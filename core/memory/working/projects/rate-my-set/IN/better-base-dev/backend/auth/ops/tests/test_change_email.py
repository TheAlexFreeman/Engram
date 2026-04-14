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
from pytest_django.asserts import assertNumQueries
from time_machine import TimeMachineFixture

from backend.accounts.models.users import User
from backend.accounts.tests.factories.users import UserFactory
from backend.auth.models.email_changes import EmailChangeRequest
from backend.auth.ops.change_email import (
    ChangeEmailTokenGenerator,
    EmailChangeRequestOps,
    FailedAttemptChangeEmailConfirmResult,
    FailedInitiateEmailChangeProcessResult,
    SuccessfulAttemptChangeEmailConfirmResult,
    SuccessfulInitiateEmailChangeProcessResultBase,
    SuccessfulInitiateEmailChangeProcessResultNotOnlyResend,
    SuccessfulInitiateEmailChangeProcessResultOnlyResend,
    attempt_change_email_confirm,
    change_email_redirect_run_preparation_logic,
    deliver_email_change_email,
    generate_change_email_link,
    initiate_email_change_process,
)
from backend.auth.ops.verify_email import VerifyEmailTokenGenerator
from backend.base.ops.emails import EmailSendResult
from backend.base.tests.helpers.auth import AuthWatcher
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions
from backend.base.tests.shared import random


@pytest.mark.django_db
class TestEmailChangeRequestOps:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

    def test_get_from_user_or_create(self):
        user = UserFactory.create()

        # 1. `user.email_change_request`
        # 2. ^ Same query as the above, but the `get` part from
        # `EmailChangeRequest.objects.get_or_create(user=user)`.
        # 3. Django's `get_or_create` currently opens a transaction/savepoint under the
        # hood, this is the opening expression.
        # 4. The insert from `EmailChangeRequest.objects.get_or_create(user=user)` since
        # it does a create.
        # 5. Close the transaction/savepoint from 3.
        with assertNumQueries(5):
            instance, created = EmailChangeRequestOps.get_from_user_or_create(user)

        assert isinstance(instance, EmailChangeRequest)
        assert created is True
        assert instance.pk is not None
        assert instance.user == user

        with assertNumQueries(0):
            instance2, created2 = EmailChangeRequestOps.get_from_user_or_create(user)

        assert isinstance(instance2, EmailChangeRequest)
        assert created2 is False
        assert instance2.pk is not None
        assert instance2.pk == instance.pk
        assert instance2.user == user
        assert instance2 == instance

        user = User.objects.get(pk=user.pk)
        with assertNumQueries(1):
            instance3, created3 = EmailChangeRequestOps.get_from_user_or_create(user)

        assert isinstance(instance3, EmailChangeRequest)
        assert created3 is False
        assert instance3.pk is not None
        assert instance3.pk == instance.pk
        assert instance3.user == user
        assert instance3 == instance

    @pytest.mark.parametrize(
        "case,previous_from_email,previous_to_email,current_from_email,new_to_email,is_new_from_or_to_email",
        [
            (
                "from_empty",
                "",
                "",
                "email1@example.com",
                "email2@example.com",
                True,
            ),
            (
                "from_email_only_changed",
                "email0@example.com",
                "email2@example.com",
                "email1@example.com",
                "email2@example.com",
                True,
            ),
            (
                "to_email_only_changed",
                "email0@example.com",
                "email1@example.com",
                "email0@example.com",
                "email2@example.com",
                True,
            ),
            (
                "both_from_and_to_email_changed",
                "email0@example.com",
                "email1@example.com",
                "email1@example.com",
                "email2@example.com",
                True,
            ),
            (
                "neither_from_nor_to_email_changed",
                "email1@example.com",
                "email1@example.com",
                "email1@example.com",
                "email1@example.com",
                False,
            ),
        ],
    )
    def test_mark_requested(
        self,
        time_machine: TimeMachineFixture,
        case: Literal[
            "from_empty",
            "from_email_only_changed",
            "to_email_only_changed",
            "both_from_and_to_email_changed",
            "neither_from_nor_to_email_changed",
        ],
        previous_from_email: str,
        previous_to_email: str,
        current_from_email: str,
        new_to_email: str,
        is_new_from_or_to_email: bool,
    ):
        ts1 = self.times.now_incremented
        time_machine.move_to(ts1, tick=False)

        initial_request_count = random.choice([0, 5])
        user = UserFactory.create(
            email=current_from_email,
        )
        ecr = EmailChangeRequest.objects.create(
            user=user,
            from_email=previous_from_email,
            to_email=previous_to_email,
            requested_at=ts1 - timedelta(microseconds=3),
            successfully_changed_at=ts1,
            last_requested_a_new_from_or_to_email_at=ts1 - timedelta(microseconds=2),
            num_times_requested_a_new_from_or_to_email=initial_request_count,
            created=ts1,
            modified=ts1,
        )

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)
        ecr_ops = EmailChangeRequestOps(ecr)

        def assert_is_now(dtv: datetime | None) -> None:
            assert dtv is not None and dtv >= ts2 and dtv <= ts2 + timedelta(minutes=3)

        ecr_ops.mark_requested(user, new_to_email)

        for indicator in (None, "refresh"):
            if indicator == "refresh":
                ecr.refresh_from_db()

            assert ecr.from_email == current_from_email
            assert ecr.to_email == new_to_email
            assert_is_now(ecr.requested_at)
            assert ecr.successfully_changed_at is None
            assert_is_now(ecr.modified)

            if is_new_from_or_to_email:
                assert_is_now(ecr.last_requested_a_new_from_or_to_email_at)
                assert (
                    ecr.num_times_requested_a_new_from_or_to_email
                    == initial_request_count + 1
                )
            else:
                assert ecr.last_requested_a_new_from_or_to_email_at == ts1 - timedelta(
                    microseconds=2
                )
                assert (
                    ecr.num_times_requested_a_new_from_or_to_email
                    == initial_request_count
                )

        other_user = UserFactory.create()
        with pytest.raises(
            ValueError,
            match=r"The `user` must match the `EmailChangeRequest` instance's `user`.",
        ):
            ecr_ops.mark_requested(other_user, "email7@example.com")

    def test_mark_sent(self, time_machine: TimeMachineFixture):
        ts1 = self.times.now_incremented
        time_machine.move_to(ts1, tick=False)

        initial_change_email_count = random.choice([0, 3])
        user = UserFactory.create()
        ecr = EmailChangeRequest.objects.create(
            user=user,
            from_email="some-from-email1@example.com",
            to_email="some-to-email1@example.com",
            requested_at=ts1 - timedelta(microseconds=2),
            last_sent_a_change_email_at=ts1 - timedelta(microseconds=1),
            num_times_sent_a_change_email=initial_change_email_count,
            created=ts1,
            modified=ts1,
        )

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)
        ecr_ops = EmailChangeRequestOps(ecr)

        def assert_is_now(dtv: datetime | None) -> None:
            assert dtv is not None and dtv >= ts2 and dtv <= ts2 + timedelta(minutes=3)

        ecr_ops.mark_sent()

        for indicator in (None, "refresh"):
            if indicator == "refresh":
                ecr.refresh_from_db()

            assert_is_now(ecr.requested_at)
            assert_is_now(ecr.last_sent_a_change_email_at)
            assert ecr.num_times_sent_a_change_email == initial_change_email_count + 1
            assert_is_now(ecr.modified)

    def test_mark_successfully_changed(self, time_machine: TimeMachineFixture):
        ts1 = self.times.now_incremented
        time_machine.move_to(ts1, tick=False)

        initial_change_count = random.choice([0, 7])
        user = UserFactory.create()
        ecr = EmailChangeRequest.objects.create(
            user=user,
            from_email="some-from-email1@example.com",
            to_email="some-to-email1@example.com",
            successfully_changed_at=None,
            last_successfully_changed_at=ts1 - timedelta(microseconds=2),
            num_times_email_successfully_changed=initial_change_count,
            created=ts1,
            modified=ts1,
        )

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)
        ecr_ops = EmailChangeRequestOps(ecr)

        def assert_is_now(dtv: datetime | None) -> None:
            assert dtv is not None and dtv >= ts2 and dtv <= ts2 + timedelta(minutes=3)

        ecr_ops.mark_successfully_changed(
            from_email=ecr.from_email, to_email=ecr.to_email
        )

        for indicator in (None, "refresh"):
            if indicator == "refresh":
                ecr.refresh_from_db()

            assert_is_now(ecr.successfully_changed_at)
            assert_is_now(ecr.last_successfully_changed_at)
            assert ecr.num_times_email_successfully_changed == initial_change_count + 1
            assert_is_now(ecr.modified)

        for from_, to_ in (
            (ecr.to_email, ecr.from_email),
            (ecr.to_email, ecr.to_email),
            (ecr.from_email, ecr.from_email),
            ("some-other-email1@example.com", "some-other-email2@example.com"),
        ):
            with pytest.raises(
                ValueError,
                match=(
                    r"The `from_email` and `to_email` must match the `EmailChangeRequest` "
                    r"instance's `from_email` and `to_email`."
                ),
            ):
                ecr_ops.mark_successfully_changed(from_email=from_, to_email=to_)


@pytest.mark.django_db
class TestChangeEmailTokenGenerator:
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

        initial_request_count = random.choice([0, 5])
        u = UserFactory.create(email="email1@example.com")
        EmailChangeRequest.objects.create(
            user=u,
            from_email="previous-from-email1@example.com",
            to_email="previous-to-email1@example.com",
            requested_at=ts1 - timedelta(microseconds=3),
            successfully_changed_at=ts1,
            last_requested_a_new_from_or_to_email_at=ts1 - timedelta(microseconds=2),
            num_times_requested_a_new_from_or_to_email=initial_request_count,
            created=ts1,
            modified=ts1,
        )

        secret_key1 = "secret-key-abcdefg-1234567-1"
        secret_key_fallback1 = "secret-key-fallback-abcdefg-1234567-1"
        secret_key_fallback2 = "secret-key-fallback-abcdefg-1234567-2"
        secret_key_fallback3_not_set = "secret-key-fallback-abcdefg-1234567-3-not-set"
        self.settings.SECRET_KEY = secret_key1
        self.settings.SECRET_KEY_FALLBACKS = [
            secret_key_fallback1,
            secret_key_fallback2,
        ]

        self.settings.CHANGE_EMAIL_TIMEOUT = int(timedelta(hours=1).total_seconds())

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)

        g = ChangeEmailTokenGenerator()

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

        initial_request_count = random.choice([0, 5])
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

        self.settings.CHANGE_EMAIL_TIMEOUT = int(timedelta(hours=1).total_seconds())

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)

        def num_seconds(dt: datetime) -> int:
            return int((dt - datetime(2001, 1, 1)).total_seconds())

        next_int_ts1 = num_seconds(datetime.now())
        g = ChangeEmailTokenGenerator()

        hv1 = g._make_hash_value(u, next_int_ts1)
        hv2 = g._make_hash_value(u, next_int_ts1)
        hv3 = g._make_hash_value(u, next_int_ts1)
        t1 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        t2 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        t3 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        assert hv1 == hv2 == hv3
        assert t1 == t2 == t3

        assert (
            EmailChangeRequest.objects.filter(user=u).update(
                from_email="previous-from-email1@example.com",
                to_email="previous-to-email1@example.com",
                requested_at=ts1 - timedelta(microseconds=3),
                successfully_changed_at=ts1,
                last_requested_a_new_from_or_to_email_at=(
                    ts1 - timedelta(microseconds=2)
                ),
                num_times_requested_a_new_from_or_to_email=initial_request_count,
                created=ts1,
                modified=ts1,
            )
            == 1
        )
        ecr = EmailChangeRequest.objects.get()
        u = User.objects.get(pk=u.pk)
        assert ecr.user == u

        hv4 = g._make_hash_value(u, next_int_ts1)
        hv5 = g._make_hash_value(u, next_int_ts1)

        assert hv4 == hv5
        assert hv4 != hv1
        assert hv5 != hv1

        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        def apply_mutation_and_check(
            source: Literal["u", "ecr"], attr: str, value: Any, should_change: bool
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

            original_value: Any
            if source == "u":
                original_value = getattr(u, attr)
                setattr(u, attr, value)
            else:
                original_value = getattr(ecr, attr)
                setattr(ecr, attr, value)
                setattr(u.email_change_request, attr, value)

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

            if source == "u":
                setattr(u, attr, original_value)
            else:
                setattr(ecr, attr, original_value)
                setattr(u.email_change_request, attr, original_value)

        apply_mutation_and_check("u", "pk", u.pk + 1, True)

        original_pw = u.password
        u.set_password("Some-Duck!@!-14#")
        next_pw = u.password
        u.set_password("Some-Duck!@!-15#")
        apply_mutation_and_check("u", "password", next_pw, True)
        u.password = original_pw

        u.last_login = ts1 - timedelta(microseconds=5)
        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        apply_mutation_and_check("u", "last_login", None, True)
        apply_mutation_and_check(
            "u", "last_login", timezone.now() + timedelta(seconds=1), True
        )
        apply_mutation_and_check("u", "email", "Email1@example.com", True)
        apply_mutation_and_check("u", "email", "email2@example.com", True)
        apply_mutation_and_check("u", "email", "EmaiL2@example.com", True)
        apply_mutation_and_check("u", "email", "EmaiL2@example.com", True)
        apply_mutation_and_check("u", "email", "email_is_verified", True)

        ecr.successfully_changed_at = ts1 - timedelta(microseconds=10)
        ecr.__class__.objects.filter(pk=ecr.pk).update(
            successfully_changed_at=ts1 - timedelta(microseconds=10)
        )
        ecr.refresh_from_db()
        u = User.objects.get(pk=u.pk)
        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        apply_mutation_and_check("ecr", "pk", ecr.pk + 100, True)
        apply_mutation_and_check(
            "ecr", "from_email", "some-other-from-email2@example.com", True
        )
        apply_mutation_and_check(
            "ecr", "to_email", "some-other-to-email2@example.com", True
        )
        apply_mutation_and_check("ecr", "successfully_changed_at", None, True)
        apply_mutation_and_check(
            "ecr",
            "successfully_changed_at",
            timezone.now() + timedelta(seconds=1),
            True,
        )

        apply_mutation_and_check("u", "email", "email1@example.com", False)
        apply_mutation_and_check(
            "ecr", "successfully_changed_at", ts1 - timedelta(microseconds=10), False
        )
        apply_mutation_and_check(
            "u", "modified", timezone.now() + timedelta(seconds=1), False
        )


@pytest.mark.django_db
class TestInitiateEmailChangeProcess:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

    @pytest.mark.parametrize(
        "only_resend",
        [
            pytest.param(True, id="only_resend"),
            pytest.param(False, id="not_only_resend"),
        ],
    )
    def test_error_email_change_request_does_not_exist(self, only_resend: bool):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(  # type: ignore[call-overload]
            user=user, to_email="use_email_change_request", only_resend=only_resend
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "use_email_change_request"
        assert r1.email_change_request is None
        assert r1.message == "There is no existing email change request to resend."
        assert r1.code == "no_existing_email_change_request"

    @pytest.mark.parametrize(
        "only_resend",
        [
            pytest.param(True, id="only_resend"),
            pytest.param(False, id="not_only_resend"),
        ],
    )
    def test_error_email_change_request_does_not_have_to_email(self, only_resend: bool):
        user = UserFactory.create(email="email1@example.com")
        ecr = EmailChangeRequest.objects.create(
            user=user, from_email=user.email, to_email=""
        )

        r1 = initiate_email_change_process(  # type: ignore[call-overload]
            user=user, to_email="use_email_change_request", only_resend=only_resend
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == ""
        assert r1.email_change_request == ecr
        assert r1.message == "There is no existing email change request to resend."
        assert r1.code == "no_existing_email_change_request"

    def test_error_empty_to_email_provided_and_only_resend(self):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(user=user, to_email="", only_resend=True)

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == ""
        assert r1.email_change_request is None
        assert r1.message == "There is no existing email change request to resend."
        assert r1.code == "no_existing_email_change_request"

    def test_error_empty_to_email_provided(self):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(user=user, to_email="", only_resend=False)

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == ""
        assert r1.email_change_request is None
        assert r1.message == "The new email cannot be blank."
        assert r1.code == "blank"

    def test_error_user_not_active(self):
        user = UserFactory.create(email="email1@example.com", is_active=False)

        r1 = initiate_email_change_process(
            user=user, to_email="email2@example.com", only_resend=False
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.email_change_request is None
        assert (
            r1.message
            == "This account is inactive. Please contact support to reactivate it."
        )
        assert r1.code == "inactive"

    def test_error_same_email(self):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(
            user=user, to_email="email1@example.com", only_resend=False
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email1@example.com"
        assert r1.email_change_request is None
        assert r1.message == "The new email is the same as the current email."
        assert r1.code == "same_email"

    def test_error_current_email_address_not_verified(self):
        user = UserFactory.create(email="email1@example.com", email_is_verified=False)

        r1 = initiate_email_change_process(
            user=user, to_email="email2@example.com", only_resend=False
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.email_change_request is None
        assert r1.message == (
            "The current email address must be verified before you can change to a "
            "new email."
        )
        assert r1.code == "current_email_requires_verification"

    @pytest.mark.parametrize(
        "conflicting_email",
        [
            "email2@example.com",
            "emaiL2@example.com",
        ],
    )
    def test_error_conflicting_user(self, conflicting_email: str):
        user1 = UserFactory.create(email="email1@example.com")
        UserFactory.create(email=conflicting_email)

        r1 = initiate_email_change_process(
            user=user1, to_email="email2@example.com", only_resend=False
        )

        assert isinstance(r1, FailedInitiateEmailChangeProcessResult)
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.email_change_request is None
        assert r1.message == "A different user already has this email."
        assert r1.code == "email_taken"

    def test_success_only_resend_email_provided(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(
            user=user, to_email="email2@example.com", only_resend=True
        )

        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultOnlyResend)
        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultBase)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert (
            r1.email_change_request is not None
            and isinstance(r1.email_change_request, EmailChangeRequest)
            and r1.email_change_request.user == user
        )
        assert r1.to_email_send_result == EmailSendResult(
            num_sent=1,
            sent_at=self.times.close_to_now,  # type: ignore[arg-type]
        )
        assert r1.from_email_send_result is None

        assert len(mailoutbox) == 1

        ea1 = EmailAssertions(mailoutbox[0])
        ea1.assert_is_change_email_to_new_email(to_email="email2@example.com")
        link = ea1.extract_change_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert ChangeEmailTokenGenerator().check_token(user, token)

    def test_success_only_resend_email_from_email_change_request(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com")
        ecr = EmailChangeRequest.objects.create(
            user=user, from_email=user.email, to_email="email2@example.com"
        )

        r1 = initiate_email_change_process(
            user=user, to_email="email2@example.com", only_resend=True
        )

        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultOnlyResend)
        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultBase)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.email_change_request == ecr
        assert r1.to_email_send_result == EmailSendResult(
            num_sent=1,
            sent_at=self.times.close_to_now,  # type: ignore[arg-type]
        )
        assert r1.from_email_send_result is None

        assert len(mailoutbox) == 1

        ea1 = EmailAssertions(mailoutbox[0])
        ea1.assert_is_change_email_to_new_email(to_email="email2@example.com")
        link = ea1.extract_change_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert ChangeEmailTokenGenerator().check_token(user, token)

    def test_success_not_only_resend_email_provided(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com")

        r1 = initiate_email_change_process(
            user=user, to_email="email2@example.com", only_resend=False
        )

        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultNotOnlyResend)
        assert isinstance(r1, SuccessfulInitiateEmailChangeProcessResultBase)
        assert r1.user == user
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert (
            r1.email_change_request is not None
            and isinstance(r1.email_change_request, EmailChangeRequest)
            and r1.email_change_request.user == user
        )
        assert r1.to_email_send_result == EmailSendResult(
            num_sent=1,
            sent_at=self.times.close_to_now,  # type: ignore[arg-type]
        )
        assert r1.from_email_send_result == EmailSendResult(
            num_sent=1,
            sent_at=self.times.close_to_now,  # type: ignore[arg-type]
        )

        assert len(mailoutbox) == 2

        ea1 = EmailAssertions(mailoutbox[0])
        ea1.assert_is_change_email_notifying_original_email(
            changing_from_email="email1@example.com",
            changing_to_email="email2@example.com",
        )

        ea2 = EmailAssertions(mailoutbox[1])
        ea2.assert_is_change_email_to_new_email(to_email="email2@example.com")
        link = ea2.extract_change_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert ChangeEmailTokenGenerator().check_token(user, token)


@pytest.mark.django_db
def test_generate_email_change_link(settings):
    user1 = UserFactory.create(id=10001, email="email1@example.com")
    g1 = generate_change_email_link(
        user1, from_email="email1@example.com", to_email="email2@example.com"
    )

    expected_token = ChangeEmailTokenGenerator().make_token(user1)
    assert expected_token, "Pre-condition"
    base_url = (settings.BASE_WEB_APP_URL or "").removesuffix("/")
    assert base_url, "Pre-condition"
    uidb64 = urlsafe_base64_encode(b"10001")
    assert uidb64 and isinstance(uidb64, str), "Pre-condition"
    assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"
    expected_link = f"{base_url}/auth/change-email/redirect/{uidb64}/{expected_token}"

    assert g1.user == user1
    assert g1.from_email == "email1@example.com"
    assert g1.to_email == "email2@example.com"
    assert g1.send_email_to == "email2@example.com"
    assert g1.secret_link == expected_link


@pytest.mark.django_db
def test_deliver_email_change_email(mailoutbox, settings, times: Times):
    user1 = UserFactory.create(id=10001, email="email1@example.com")
    g1 = generate_change_email_link(
        user1, from_email="email1@example.com", to_email="email2@example.com"
    )

    expected_token = ChangeEmailTokenGenerator().make_token(user1)
    assert expected_token, "Pre-condition"
    base_url = (settings.BASE_WEB_APP_URL or "").removesuffix("/")
    assert base_url, "Pre-condition"
    uidb64 = urlsafe_base64_encode(b"10001")
    assert uidb64 and isinstance(uidb64, str), "Pre-condition"
    assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"
    expected_link = f"{base_url}/auth/change-email/redirect/{uidb64}/{expected_token}"

    assert g1.secret_link == expected_link

    assert len(mailoutbox) == 0, "Pre-condition"

    d1 = deliver_email_change_email(
        user=user1,
        from_email="email1@example.com",
        to_email="email2@example.com",
        secret_link=g1.secret_link,
    )

    assert d1.user == user1
    assert d1.from_email == "email1@example.com"
    assert d1.to_email == "email2@example.com"
    assert d1.sent_email_to == "email2@example.com"
    assert d1.email_send_result == EmailSendResult(
        num_sent=1,
        sent_at=times.close_to_now,  # type: ignore[arg-type]
    )

    assert len(mailoutbox) == 1

    ea1 = EmailAssertions(mailoutbox[0])
    ea1.assert_is_change_email_to_new_email(to_email="email2@example.com")
    link = ea1.extract_change_email_link()

    assert link
    token = link.rsplit("/", 1)[1]
    assert ChangeEmailTokenGenerator().check_token(user1, token)
    assert token == expected_token


@pytest.mark.django_db
class TestChangeEmailRedirectRunPreparationLogic:
    def test_using_reset_url_token(self):
        user1 = UserFactory.create(id=10001, email="email1@example.com")
        uidb64 = urlsafe_base64_encode(b"10001")

        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"

        session: dict[str, Any] = {}
        request = SimpleNamespace(session=session)

        r = change_email_redirect_run_preparation_logic(
            request=request,  # type: ignore[arg-type]
            uidb64=uidb64,
            secret_token="change-email",
        )

        assert r.uidb64 == uidb64
        assert r.secret_token_to_use == "change-email"
        assert r.did_set_secret_token_in_session is False
        assert session == {}

    def test_not_using_reset_url_token(self):
        user1 = UserFactory.create(id=10001, email="email1@example.com")
        uidb64 = urlsafe_base64_encode(b"10001")

        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"

        session: dict[str, Any] = {}
        request = SimpleNamespace(session=session)

        r = change_email_redirect_run_preparation_logic(
            request=request,  # type: ignore[arg-type]
            uidb64=uidb64,
            secret_token="t123",
        )

        assert r.uidb64 == uidb64
        assert r.secret_token_to_use == "change-email"
        assert r.did_set_secret_token_in_session is True
        assert session == {"change_email_token": "t123"}


@pytest.mark.django_db
class TestAttemptChangeEmailConfirm:
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

    def test_error_no_user(self):
        user1 = UserFactory.create(id=10001, email="email1@example.com")
        uidb64 = urlsafe_base64_encode(b"10001")

        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"

        user1.delete()

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token="t123",
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == "t123"
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.user is None
        assert r1.from_email is None
        assert r1.to_email is None
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. Please "
            "request another link to change your email."
        )
        assert r1.code == "invalid"

    def test_error_no_email_change_request(self):
        user1 = UserFactory.create(email="email1@example.com")

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token="t123",
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == "t123"
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.user == user1
        assert r1.from_email is None
        assert r1.to_email is None
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. Please "
            "request another link to change your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "from_email, to_email",
        [
            ("email1@example.com", ""),
            ("email0@example.com", ""),
            ("", "email2@example.com"),
            ("", ""),
        ],
    )
    def test_error_not_from_email_or_not_to_email(self, from_email: str, to_email: str):
        user1 = UserFactory.create(email="email1@example.com")
        EmailChangeRequest.objects.create(
            user=user1, from_email=from_email, to_email=to_email
        )

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token="t123",
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == "t123"
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.user == user1
        assert r1.from_email == from_email
        assert r1.to_email == to_email
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. Please "
            "request another link to change your email."
        )
        assert r1.code == "invalid"

    def test_error_reset_url_token_no_secret_token_from_session(self):
        user1 = UserFactory.create(email="email1@example.com")
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token="change-email",
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == "change-email"
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is True
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. Please "
            "request another link to change your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session, secret_token",
        [
            (True, "t123"),
            (False, "t123"),
            (True, "vfg"),
            (False, "vfg"),
            (True, "rpg"),
            (False, "rpg"),
        ],
    )
    def test_error_invalid_token(self, set_in_session: bool, secret_token: str):
        user1 = UserFactory.create(email="email1@example.com")
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )

        if secret_token == "vfg":
            secret_token = VerifyEmailTokenGenerator().make_token(user1)
        elif secret_token == "rpg":
            secret_token = PasswordResetTokenGenerator().make_token(user1)

        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=use_secret_token,
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. Please "
            "request another link to change your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_error_user_inactive(self, set_in_session: bool):
        user1 = UserFactory.create(email="email1@example.com", is_active=False)
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=use_secret_token,
            password="does-not-matter",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert r1.code == "inactive"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_error_missing_password(self, set_in_session: bool):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=use_secret_token,
            password="",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == "Please enter the password."
        assert r1.code == "missing_password"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_error_incorrect_password(self, set_in_session: bool):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=use_secret_token,
            password=f"{self.strong_password}_",
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == "Incorrect password."
        assert r1.code == "incorrect_password"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "conflicting_email",
        [
            "email2@example.com",
            "emaiL2@example.com",
        ],
    )
    def test_error_conflicting_user(self, set_in_session: bool, conflicting_email: str):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        UserFactory.create(email=conflicting_email)
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=use_secret_token,
            password=self.strong_password,
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == "A different user already has this email."
        assert r1.code == "email_taken"

    def test_error_with_already_retrieved_uidb64_user(self):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password + "_2"
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        EmailChangeRequest.objects.create(
            user=user2, from_email="email2@example.com", to_email="email3@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=secret_token,
            password=self.strong_password,
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=user2,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.user == user2
        assert r1.from_email == "email2@example.com"
        assert r1.to_email == "email3@example.com"
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. "
            "Please request another link to change your email."
        )
        assert r1.code == "invalid"

    def test_error_without_already_retrieved_uidb64_user(self):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password + "_2"
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        EmailChangeRequest.objects.create(
            user=user2, from_email="email2@example.com", to_email="email3@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1) + "_1"
        assert secret_token, "Pre-condition"

        r1 = attempt_change_email_confirm(
            request=self.request,
            uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
            secret_token=secret_token,
            password=self.strong_password,
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is None
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False
        assert r1.message == (
            "The email change link you followed either has expired or is invalid. "
            "Please request another link to change your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_only_check_validation_conditions(self, set_in_session: bool):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email4@example.com", password=self.strong_password + "_2"
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        EmailChangeRequest.objects.create(user=user2)
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        with auth_watcher.expect_no_user_login(user1):
            r1 = attempt_change_email_confirm(
                request=self.request,
                uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
                secret_token=use_secret_token,
                password=self.strong_password,
                only_check_validation_conditions=True,
                check_password=True,
                login_if_successful=True,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r1, SuccessfulAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is True
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is False

        user1.refresh_from_db()
        assert user1.email == "email1@example.com"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_with_already_retrieved_uidb64_user_only_check_validation_conditions(
        self, set_in_session: bool
    ):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password + "_2"
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        EmailChangeRequest.objects.create(
            user=user2, from_email="email2@example.com", to_email="email3@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        user2 = User.objects.get(pk=user2.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        with (
            auth_watcher.expect_no_user_login(user1),
            auth_watcher.expect_no_user_login(user2),
        ):
            r1 = attempt_change_email_confirm(
                request=self.request,
                uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
                secret_token=use_secret_token,
                password=self.strong_password + "_2",
                only_check_validation_conditions=True,
                check_password=True,
                login_if_successful=True,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r1, SuccessfulAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is True
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user2
        assert r1.from_email == "email2@example.com"
        assert r1.to_email == "email3@example.com"
        assert r1.did_login is False

        user1.refresh_from_db()
        assert user1.email == "email1@example.com"

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
    @pytest.mark.parametrize(
        "initial_email_is_verified",
        [
            pytest.param(True, id="initial_email_is_verified"),
            pytest.param(False, id="initial_email_is_not_verified"),
        ],
    )
    def test_success_without_already_retrieved_uidb64_user(
        self,
        set_in_session: bool,
        should_login: bool,
        initial_email_is_verified: bool,
    ):
        user1 = UserFactory.create(
            email="email1@example.com",
            password=self.strong_password,
            email_is_verified=initial_email_is_verified,
        )
        user2 = UserFactory.create(
            email="email4@example.com", password=self.strong_password + "_2"
        )
        ecr1 = EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        EmailChangeRequest.objects.create(user=user2)
        user1 = User.objects.get(pk=user1.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        ts1 = timezone.now()
        with (
            auth_watcher.expect_user_login(user1)
            if should_login
            else auth_watcher.expect_no_user_login(user1)
        ):
            r1 = attempt_change_email_confirm(
                request=self.request,
                uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
                secret_token=use_secret_token,
                password=self.strong_password,
                only_check_validation_conditions=False,
                check_password=True,
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r1, SuccessfulAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user1
        assert r1.from_email == "email1@example.com"
        assert r1.to_email == "email2@example.com"
        assert r1.did_login is should_login

        user1.refresh_from_db()
        ecr1.refresh_from_db()
        assert user1.email == "email2@example.com"
        assert user1.email_is_verified is True
        assert (
            user1.email_verified_as_of is not None and user1.email_verified_as_of >= ts1
        )
        assert ecr1.from_email == "email1@example.com"
        assert ecr1.to_email == "email2@example.com"
        assert (
            ecr1.last_successfully_changed_at
            and ecr1.last_successfully_changed_at >= ts1
        )
        assert ecr1.successfully_changed_at and ecr1.successfully_changed_at >= ts1

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
    @pytest.mark.parametrize(
        "initial_email_is_verified",
        [
            pytest.param(True, id="initial_email_is_verified"),
            pytest.param(False, id="initial_email_is_not_verified"),
        ],
    )
    def test_success_with_already_retrieved_uidb64_user(
        self,
        set_in_session: bool,
        should_login: bool,
        initial_email_is_verified: bool,
    ):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email2@example.com",
            password=self.strong_password + "_2",
            email_is_verified=initial_email_is_verified,
        )
        EmailChangeRequest.objects.create(
            user=user1, from_email="email1@example.com", to_email="email2@example.com"
        )
        ecr2 = EmailChangeRequest.objects.create(
            user=user2, from_email="email2@example.com", to_email="email3@example.com"
        )
        user1 = User.objects.get(pk=user1.pk)
        user2 = User.objects.get(pk=user2.pk)
        secret_token = ChangeEmailTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "change-email" if set_in_session else secret_token
        if set_in_session:
            self.session["change_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        ts1 = timezone.now()
        with (
            auth_watcher.expect_user_login(user2)
            if should_login
            else auth_watcher.expect_no_user_login(user2)
        ):
            r1 = attempt_change_email_confirm(
                request=self.request,
                uidb64=urlsafe_base64_encode(force_bytes(user1.pk)),
                secret_token=use_secret_token,
                password=self.strong_password + "_2",
                only_check_validation_conditions=False,
                check_password=True,
                login_if_successful=should_login,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r1, SuccessfulAttemptChangeEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == use_secret_token
        assert r1.only_check_validation_conditions is False
        assert r1.checked_password is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.user == user2
        assert r1.from_email == "email2@example.com"
        assert r1.to_email == "email3@example.com"
        assert r1.did_login is should_login

        user2.refresh_from_db()
        ecr2.refresh_from_db()
        assert user2.email == "email3@example.com"
        assert user2.email_is_verified is True
        assert (
            user2.email_verified_as_of is not None and user2.email_verified_as_of >= ts1
        )
        assert ecr2.from_email == "email2@example.com"
        assert ecr2.to_email == "email3@example.com"
        assert (
            ecr2.last_successfully_changed_at
            and ecr2.last_successfully_changed_at >= ts1
        )
        assert ecr2.successfully_changed_at and ecr2.successfully_changed_at >= ts1
