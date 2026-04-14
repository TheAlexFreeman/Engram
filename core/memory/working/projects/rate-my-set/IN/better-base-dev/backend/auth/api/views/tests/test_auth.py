from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

import pytest
from dirty_equals import IsStr
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.models import Session
from django.template import RequestContext
from django.test.client import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import ErrorDetail
from rest_framework.test import APIClient

from backend.accounts.api.serializers.users import UserReadOnlySerializer
from backend.accounts.models import User
from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.memberships import Membership
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom
from backend.auth.api.serializers.auth import ChangeEmailRetrieveSerializer
from backend.auth.models.email_changes import EmailChangeRequest
from backend.auth.ops.change_email import ChangeEmailTokenGenerator
from backend.auth.ops.verify_email import VerifyEmailTokenGenerator
from backend.base.templatetags.initial_server_data_provided_for_web import (
    get_all_data,
    get_user_data,
)
from backend.base.tests.helpers.auth import AuthWatcher, UserEmail
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions
from backend.base.tests.helpers.initial_server_data_provided_for_web import (
    extract_initial_data,
)


@pytest.mark.django_db
class BaseTestAuthViewSet:
    @pytest.fixture(autouse=True)
    def setup(
        self, times: Times, settings, client: Client, api_client: APIClient
    ) -> None:
        self.times = times
        self.settings = settings
        self.client = client
        self.api_client = api_client

    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"


class TestSignup(BaseTestAuthViewSet):
    endpoint = "/api/auth/signup"

    def post(self, **data: str):
        data.setdefault("email", "email1@example.com")
        data.setdefault("first_name", "Some")
        data.setdefault("last_name", "Name")
        data.setdefault("password", self.strong_password)
        data.setdefault("password_confirm", self.strong_password)
        return self.api_client.post(self.endpoint, data=data)

    def test_logs_user_out_if_authenticated(self, user: User):
        self.api_client.force_login(user)
        s = Session.objects.get()
        assert s and s.session_key and s.session_data and s.expire_date, (
            "Current pre-condition"
        )

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_logout(user=user, assert_counter_equals=1):
            response = self.api_client.post(
                self.endpoint,
                data={
                    "email": "email1@example.com",
                    "first_name": "Some",
                    "last_name": "Name",
                    "password": self.strong_password,
                    "password_confirm": self.strong_password,
                },
            )
        assert response.status_code == 201, "Current pre-condition"

        with pytest.raises(Session.DoesNotExist):
            s.refresh_from_db()

    def test_invalid_email(self):
        r = self.post(email="invalid")
        assert r.status_code == 400
        assert r.data == {"email": ["Enter a valid email address."]}

    def test_invalid_password(self):
        r = self.post(password="12345")
        assert r.status_code == 400
        assert r.data == {
            "password": [
                "This password is too short. It must contain at least 9 characters.",
                "This password is too common.",
                "This password is entirely numeric.",
                "Please include at least one special character (!@#$&*%?) in your password",
            ]
        }

    def test_passwords_do_not_match(self):
        r = self.post(password_confirm="different")
        assert r.status_code == 400
        assert r.data == {"password_confirm": ["Passwords do not match."]}

    @pytest.mark.parametrize("case", ["exact", "case_insensitive"])
    def test_existing_user(self, case: Literal["exact", "case_insensitive"]):
        if case == "exact":
            UserFactory.create(email="email1@example.com")
            email = "email1@example.com"
        else:
            UserFactory.create(email="EmaiL1@example.com")
            email = "eMaIl1@example.com"

        r = self.post(email=email)
        assert r.data == {
            "non_field_errors": [
                "An account with that email address already exists. Either log in or "
                "double check the provided info and try again."
            ],
            "_main_code_": "existing_user",
        }

    def test_domain_blocked(self):
        self.settings.SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS = True
        self.settings.SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS = [
            "duck.com",
            "goose.com",
        ]
        self.settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION = False

        r = self.post()
        assert r.data == {
            "non_field_errors": [
                'The email "email1@example.com" is not allowed to sign up at this time.'
            ],
            "_main_code_": "email_not_allowed_for_signup",
        }

    def test_successful(self, mailoutbox):
        assert User.objects.count() == 0, "Current pre-condition"
        assert Account.objects.count() == 0, "Current pre-condition"
        assert Membership.objects.count() == 0, "Current pre-condition"
        assert Session.objects.count() == 0, "Current pre-condition"

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_login(
            UserEmail("email1@example.com"),
            assert_counter_equals=1,
        ):
            r = self.post()
        assert r.status_code == 201

        user = User.objects.get()
        account = Account.objects.get()
        membership = Membership.objects.get()
        session = Session.objects.get()

        # NOTE: `ur` stands for "underlying request", currently referring to the Django
        # `HttpRequest` object.
        ur = r.wsgi_request
        assert r.data == get_all_data(
            context=RequestContext(ur), request=ur, camel_case=False
        ) | {
            # The CSRF token extracted from `ur` will be different (likely) from the
            # actual correct one in these tests. That's fine, this (the `"csrf_token"`
            # exact comparison checking for correct logic) should be tested elsewhere.
            "csrf_token": IsStr(min_length=20),
            "signup_user": UserReadOnlySerializer(instance=user).data,
        }

        assert user.email == "email1@example.com"
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None
        assert user.name == "Some Name"
        assert user.is_staff is False
        assert user.is_superuser is False
        assert self.times.is_close_to_now(user.date_joined)
        assert user.created_from == UserCreatedFrom.DIRECT_SIGNUP
        assert not user.uploaded_profile_image
        assert user.created == user.date_joined
        assert user.modified >= user.created

        assert account.account_type == AccountType.PERSONAL
        assert account.name == "Personal Account"
        assert not account.uploaded_profile_image
        assert self.times.is_close_to_now(account.created)
        assert self.times.is_close_to_now(account.modified)

        assert membership.account == account
        assert membership.user == user
        assert membership.role == Role.OWNER
        assert self.times.is_close_to_now(membership.last_selected_at)
        assert self.times.is_close_to_now(membership.created)
        assert self.times.is_close_to_now(membership.modified)

        assert session.session_key and session.session_data and session.expire_date, (
            "Sanity check"
        )

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email=user.email)
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user, token)


class TestSignupResendVerificationEmail(BaseTestAuthViewSet):
    endpoint = "/api/auth/signup/resend-verification-email"

    def post(self, **data: str):
        data.setdefault("email", "email1@example.com")
        return self.api_client.post(self.endpoint, data=data)

    def test_user_not_authenticated(self):
        r = self.post()
        assert r.status_code == 403
        assert r.data == {"detail": "Authentication credentials were not provided."}

    def test_invalid_email(self):
        user = UserFactory.create()
        self.api_client.force_login(user)
        r = self.post(email="invalid")
        assert r.status_code == 400
        assert r.data == {"email": ["Enter a valid email address."]}

    def test_already_verified(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com", email_is_verified=True)
        self.api_client.force_login(user)
        r = self.post()
        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": [
                (
                    "You have already verified your current email address on file. Please "
                    "refresh the page, re-login, or navigate to the home page to continue."
                )
            ],
            "_main_code_": "already_verified",
        }

        assert len(mailoutbox) == 0

    def test_email_taken(self, mailoutbox):
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        self.api_client.force_login(user1)

        # Test with another unverified email.
        user2 = UserFactory.create(
            email="email2@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        r = self.post(email=user2.email)
        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": [
                (
                    "That email address is already regisered to another account. "
                    "Either choose a different email address or log in to the existing account."
                )
            ],
            "_main_code_": "email_taken",
        }

        assert len(mailoutbox) == 0

        # Test with a verified email.
        user3 = UserFactory.create(email="email3@example.com")
        assert user3.email_is_verified, "Current pre-condition"
        assert user3.email_verified_as_of is not None, "Current pre-condition"

        r = self.post(email=user3.email)
        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": [
                (
                    "That email address is already regisered to another account. "
                    "Either choose a different email address or log in to the existing account."
                )
            ],
            "_main_code_": "email_taken",
        }

        assert len(mailoutbox) == 0

    @pytest.mark.parametrize("email_to_use", ["from_user", "new_email"])
    def test_successful(self, mailoutbox, email_to_use):
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        self.api_client.force_login(user1)
        assert not user1.email_is_verified, "Current pre-condition"
        assert not user1.email_verified_as_of, "Current pre-condition"

        if email_to_use == "from_user":
            r = self.post(email=user1.email)
        else:
            r = self.post(email="email4@example.com")
        assert r.status_code == 200

        user = User.objects.get()

        if email_to_use == "new_email":
            assert user.email == "email4@example.com"
        else:
            assert user.email == "email1@example.com"

        # NOTE: `ur` stands for "underlying request", currently referring to the Django
        # `HttpRequest` object.
        ur = r.wsgi_request
        assert r.data == get_all_data(
            context=RequestContext(ur), request=ur, camel_case=False
        ) | {
            # The CSRF token extracted from `ur` will be different (likely) from the
            # actual correct one in these tests. That's fine, this (the `"csrf_token"`
            # exact comparison checking for correct logic) should be tested elsewhere.
            "csrf_token": IsStr(min_length=20),
        }

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email=user.email)
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user, token)


class TestChangeEmailFlow(BaseTestAuthViewSet):
    endpoint_retrieve = "/api/auth/change-email/retrieve"
    endpoint_request = "/api/auth/change-email/request"
    endpoint_resend = "/api/auth/change-email/resend"
    endpoint_confirm = "/api/auth/change-email/confirm"

    @pytest.mark.parametrize("case", ["existing", "no_existing"])
    def test_retrieve(self, case: Literal["existing", "no_existing"]):
        user = UserFactory.create(email="email1@example.com")
        self.api_client.force_login(user)
        initial_ecr: EmailChangeRequest | None = None
        if case == "existing":
            initial_ecr = EmailChangeRequest.objects.create(
                user=user,
                from_email="email7@example.com",
                to_email="email8@example.com",
            )
        response = self.api_client.get(self.endpoint_retrieve)
        assert response.status_code == 200

        if case == "existing":
            assert (
                response.data
                == ChangeEmailRetrieveSerializer(instance=initial_ecr).data
            )
            assert EmailChangeRequest.objects.count() == 1
        else:
            assert (
                response.data
                == ChangeEmailRetrieveSerializer(
                    instance=EmailChangeRequest(id=-1, user=user)
                ).data
            )
            assert EmailChangeRequest.objects.count() == 0

    @pytest.mark.parametrize("case", ["existing", "no_existing"])
    def test_request(self, case: Literal["existing", "no_existing"], mailoutbox):
        user = UserFactory.create(email="email1@example.com")
        self.api_client.force_login(user)
        initial_ecr: EmailChangeRequest | None = None
        if case == "existing":
            initial_ecr = EmailChangeRequest.objects.create(
                user=user,
                from_email="email7@example.com",
                to_email="email8@example.com",
            )
        r1 = self.api_client.post(
            self.endpoint_request, data={"to_email": "email2@example.com"}
        )

        if case == "existing":
            assert initial_ecr is not None, "Pre-condition"
            ecr = initial_ecr
            ecr.refresh_from_db()
        else:
            ecr = EmailChangeRequest.objects.get()

        assert r1.status_code == 200
        assert r1.data == ChangeEmailRetrieveSerializer(instance=ecr).data
        assert ecr.user == user
        assert ecr.from_email == "email1@example.com"
        assert ecr.to_email == "email2@example.com"
        assert EmailChangeRequest.objects.count() == 1
        assert len(mailoutbox) == 2

        ea1 = EmailAssertions(mailoutbox[0])
        ea2 = EmailAssertions(mailoutbox[1])

        ea1.assert_is_change_email_notifying_original_email(
            changing_from_email="email1@example.com",
            changing_to_email="email2@example.com",
        )
        ea2.assert_is_change_email_to_new_email(to_email="email2@example.com")
        link = ea2.extract_change_email_link()
        assert link
        token = link.rsplit("/", 1)[1]
        assert ChangeEmailTokenGenerator().check_token(user, token)

        # Check that serializer validation is happening.
        r2 = self.api_client.post(self.endpoint_request, data={"to_email": "invalid"})
        assert r2.status_code == 400
        assert r2.data == {"to_email": ["Enter a valid email address."]}

        # Check that the current email address is verified first.
        user.email_is_verified = False
        user.save(update_fields=["email_is_verified", "modified"])
        r3 = self.api_client.post(
            self.endpoint_request, data={"to_email": "email2@example.com"}
        )
        assert r3.status_code == 403
        assert r3.data == {
            "detail": "You must verify your email before you can perform this action."
        }

        # Check that op errors are handled.
        user.email = "email2@example.com"
        user.email_is_verified = True
        user.email_verified_as_of = self.times.now
        user.save(
            update_fields=[
                "email",
                "email_is_verified",
                "email_verified_as_of",
                "modified",
            ]
        )
        r3 = self.api_client.post(
            self.endpoint_request, data={"to_email": "email2@example.com"}
        )
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": ["The new email is the same as the current email."],
            "_main_code_": "same_email",
        }

    @pytest.mark.parametrize("case", ["existing", "no_existing"])
    def test_resend(self, case: Literal["existing", "no_existing"], mailoutbox):
        user1 = UserFactory.create(email="email1@example.com")
        user2 = UserFactory.create(email="email2@example.com")
        self.api_client.force_login(user1)
        ecr: EmailChangeRequest | None = None
        if case == "existing":
            ecr = EmailChangeRequest.objects.create(
                user=user1,
                from_email="email1@example.com",
                to_email="email8@example.com",
            )
        EmailChangeRequest.objects.create(
            user=user2,
            from_email="email2@example.com",
            to_email="email3@example.com",
        )
        r1 = self.api_client.post(self.endpoint_resend, data={})

        if case == "no_existing":
            assert r1.status_code == 400
            assert r1.data == {
                "non_field_errors": [
                    "There is no existing email change request to resend."
                ],
                "_main_code_": "no_existing_email_change_request",
            }

            return

        assert ecr is not None, "Pre-condition"
        ecr.refresh_from_db()

        assert r1.status_code == 200
        assert r1.data == ChangeEmailRetrieveSerializer(instance=ecr).data
        assert ecr.user == user1
        assert ecr.from_email == "email1@example.com"
        assert ecr.to_email == "email8@example.com"
        assert EmailChangeRequest.objects.count() == 2
        assert len(mailoutbox) == 1

        ea1 = EmailAssertions(mailoutbox[0])

        ea1.assert_is_change_email_to_new_email(to_email="email8@example.com")
        link = ea1.extract_change_email_link()
        assert link
        token = link.rsplit("/", 1)[1]
        assert ChangeEmailTokenGenerator().check_token(user1, token)

        # Check that the current email address is verified first.
        user1.email_is_verified = False
        user1.save(update_fields=["email_is_verified", "modified"])
        r2 = self.api_client.post(self.endpoint_resend, data={})
        assert r2.status_code == 403
        assert r2.data == {
            "detail": "You must verify your email before you can perform this action."
        }

        # Check that op errors are handled.
        user1.email = "email8@example.com"
        user1.email_is_verified = True
        user1.email_verified_as_of = self.times.now
        user1.save(
            update_fields=[
                "email",
                "email_is_verified",
                "email_verified_as_of",
                "modified",
            ]
        )
        r3 = self.api_client.post(self.endpoint_resend, data={})
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": ["The new email is the same as the current email."],
            "_main_code_": "same_email",
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    def test_change_email_confirm_error_with_uidb64(
        self, key_variant: Literal["uidb_64", "uidb64"]
    ):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        EmailChangeRequest.objects.create(
            user=user1,
            from_email="email1@example.com",
            to_email="email8@example.com",
        )
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk + 1)),
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The email change link you followed either has expired "
                "or is invalid. Please request another link to change "
                "your email."
            ],
            "_main_code_": "invalid",
        }

        r2 = self.api_client.post(
            self.endpoint_confirm,
            data={
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r2.status_code == 400
        assert r2.data == {
            "uidb64": [ErrorDetail(string="This field is required.", code="required")]
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    @pytest.mark.parametrize(
        "secret_token_case",
        ["session_but_missing", "incorrect"],
    )
    def test_change_email_confirm_error_with_secret_token(
        self,
        key_variant: Literal["uidb_64", "uidb64"],
        secret_token_case: Literal["session_but_missing", "incorrect"],
    ):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        EmailChangeRequest.objects.create(
            user=user1,
            from_email="email1@example.com",
            to_email="email8@example.com",
        )
        secret_token = (
            ChangeEmailTokenGenerator().make_token(user1) + "_"
            if secret_token_case == "incorrect"
            else "change-email"
        )
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The email change link you followed either has expired "
                "or is invalid. Please request another link to change "
                "your email."
            ],
            "_main_code_": "invalid",
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    def test_change_email_confirm_error_with_password(
        self, key_variant: Literal["uidb_64", "uidb64"]
    ):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        EmailChangeRequest.objects.create(
            user=user1,
            from_email="email1@example.com",
            to_email="email8@example.com",
        )
        secret_token = ChangeEmailTokenGenerator().make_token(user1)
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "secret_token": secret_token,
                "password": self.strong_password + "_",
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": ["Incorrect password."],
            "_main_code_": "incorrect_password",
        }

    @pytest.mark.parametrize(
        "secret_token_variant", ["pulled_from_session", "set_explicitly"]
    )
    @pytest.mark.parametrize(
        "user_is_logged_in_while_confirming",
        [
            pytest.param(True, id="user_is_logged_in_while_confirming"),
            pytest.param(False, id="user_is_not_logged_in_while_confirming"),
        ],
    )
    def test_change_email_confirm_full_flow(
        self,
        mailoutbox,
        secret_token_variant: Literal["pulled_from_session", "set_explicitly"],
        user_is_logged_in_while_confirming: bool,
    ):
        # Set up everything, and then post to the resend endpoint to get the email sent.
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password + "_2"
        )
        self.api_client.force_login(user1)

        client = APIClient()
        if user_is_logged_in_while_confirming:
            client.force_login(user1)

        ecr = EmailChangeRequest.objects.create(
            user=user1,
            from_email="email1@example.com",
            to_email="email8@example.com",
        )
        EmailChangeRequest.objects.create(
            user=user2,
            from_email="email2@example.com",
            to_email="email3@example.com",
        )
        r0 = self.api_client.post(self.endpoint_resend, data={})

        # Extract the link from the email, and grab the necessary information for the
        # next steps.
        ecr.refresh_from_db()
        user1 = User.objects.get(pk=user1.pk)
        assert r0.status_code == 200, "Pre-condition"
        assert len(mailoutbox) == 1, "Pre-condition"
        ea1 = EmailAssertions(mailoutbox[0])
        link = ea1.extract_change_email_link()
        assert link, "Pre-condition"
        _, uidb64, secret_token = link.rsplit("/", 2)
        assert uidb64 and urlsafe_base64_encode(force_bytes(user1.pk)) == uidb64, (
            "Pre-condition"
        )
        assert secret_token and ChangeEmailTokenGenerator().check_token(
            user1, secret_token
        ), "Pre-condition"

        # Simulate the actual flow the API flow that would happen when the user follows
        # the link, and then the frontend sends the request to the API.
        client = APIClient()
        r11 = Client.get(client, link, follow=False)
        next_link = r11.headers["Location"]

        assert r11.status_code == 302
        assert next_link != link
        assert next_link == f"/auth/change-email/confirm/{uidb64}/change-email"

        r12 = Client.get(client, next_link, follow=False)

        assert r12.status_code == 200
        initial_data = extract_initial_data(r12)
        assert initial_data["extra"] == {
            "changeEmailConfirm": {
                "isValid": True,
                "secretToken": "change-email",
                "uidb64": uidb64,
            },
            "signaling": {
                "immediatelyRedirectTo": "changeEmailConfirm",
            },
        }

        secret_token_for_confirm = (
            secret_token if secret_token_variant == "set_explicitly" else "change-email"
        )

        r131 = client.post(
            self.endpoint_confirm,
            data={"uidb64": uidb64, "secret_token": secret_token_for_confirm},
        )

        assert r131.status_code == 400
        assert r131.data == {
            "password": [ErrorDetail(string="This field is required.", code="required")]
        }

        r132 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
                "password": self.strong_password + "_2",
            },
        )

        assert r132.status_code == 400
        assert r132.data == {
            "non_field_errors": [
                "Incorrect password.",
            ],
            "_main_code_": "incorrect_password",
        }

        ts_pre_r133 = self.times.now
        r133 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
                "password": self.strong_password,
            },
        )
        ur133 = r133.wsgi_request
        user1.refresh_from_db()
        ur133.user = user1

        assert r133.status_code == 200
        assert r133.data == get_all_data(
            context=RequestContext(ur133), request=ur133, camel_case=False
        ) | {
            "csrf_token": IsStr(min_length=20),
            "email_just_changed_to": "email8@example.com",
        }

        ecr.refresh_from_db()

        assert user1.email == "email8@example.com"
        assert user1.email_is_verified is True
        assert (
            user1.email_verified_as_of is not None
            and user1.email_verified_as_of >= ts_pre_r133
            and (user1.email_verified_as_of <= ts_pre_r133 + timedelta(minutes=3))
        )

        assert ecr.from_email == "email1@example.com"
        assert ecr.to_email == "email8@example.com"
        assert (
            ecr.successfully_changed_at is not None
            and ecr.successfully_changed_at >= ts_pre_r133
            and (ecr.successfully_changed_at <= ts_pre_r133 + timedelta(minutes=3))
        )
        assert (
            ecr.last_successfully_changed_at is not None
            and ecr.last_successfully_changed_at >= ts_pre_r133
            and (ecr.last_successfully_changed_at <= ts_pre_r133 + timedelta(minutes=3))
        )
        assert ecr.num_times_email_successfully_changed == 1

        # Now that we've checked the success case, let's verify that re-following the
        # link and/or re-submitting to the confirm API endpoint fails. These links
        # should only be able to be used once, and we're confirming that with this part
        # of this test.

        client = APIClient()
        r41 = Client.get(client, link, follow=False)
        next_link = r41.headers["Location"]

        # The redirect should still continue as expected.
        assert r41.status_code == 302
        assert next_link != link
        assert next_link == f"/auth/change-email/confirm/{uidb64}/change-email"

        r42 = Client.get(client, next_link, follow=False)

        # We should land successfully on the frontend, but have `isValid` set to `False`
        # with `errorCode` and `errorMessage` set to the appropriate values. The
        # frontend will check for those and display a proper error page with proper
        # error message.
        assert r42.status_code == 200
        initial_data = extract_initial_data(r42)
        assert initial_data["extra"] == {
            "changeEmailConfirm": {
                "isValid": False,
                "secretToken": "change-email",
                "uidb64": uidb64,
                "errorCode": "invalid",
                "errorMessage": (
                    "The email change link you followed either has expired or is "
                    "invalid. Please request another link to change your email."
                ),
            },
            "signaling": {
                "immediatelyRedirectTo": "changeEmailConfirm",
            },
        }

        r51 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
                "password": self.strong_password,
            },
        )

        assert r51.status_code == 400
        assert r51.data == {
            "non_field_errors": [
                (
                    "The email change link you followed either has expired or is "
                    "invalid. Please request another link to change your email."
                )
            ],
            "_main_code_": "invalid",
        }


class TestVerifyEmail(BaseTestAuthViewSet):
    endpoint_send = "/api/auth/verify-email/send"
    endpoint_confirm = "/api/auth/verify-email/confirm"

    def send(self, *, email: str = "email1@example.com"):
        return self.api_client.post(self.endpoint_send, data={"email": email})

    def confirm(self, **data: str):
        return self.api_client.post(self.endpoint_confirm, data=data)

    def test_send_error_no_user(self, mailoutbox):
        r1 = self.send()
        assert r1.status_code == 400
        assert r1.data == {
            "_main_code_": "no_user",
            "non_field_errors": [
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ],
        }

        assert len(mailoutbox) == 0

    def test_send_error_invalid_email(self, mailoutbox):
        r1 = self.send(email="invalid")
        assert r1.status_code == 400
        assert r1.data == {"email": ["Enter a valid email address."]}

        assert len(mailoutbox) == 0

    def test_send_error_already_verified(self, mailoutbox):
        user1 = UserFactory.create(email="email1@example.com")
        r1 = self.send(email=user1.email)
        assert r1.status_code == 400
        assert r1.data == {
            "_main_code_": "already_verified",
            "non_field_errors": ["This email is already verified."],
        }

        assert len(mailoutbox) == 0

    def test_send_successful(self, mailoutbox):
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        r1 = self.send(email=user1.email)
        assert r1.status_code == 200
        assert r1.data == {}

        assert len(mailoutbox) == 1

        ea1 = EmailAssertions(mailoutbox[0])
        ea1.assert_is_verification_email(to_email=user1.email)
        link = ea1.extract_verification_email_link()
        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user1, token)

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    def test_verify_email_confirm_error_with_uidb64(
        self, key_variant: Literal["uidb_64", "uidb64"]
    ):
        user1 = UserFactory.create(email="email1@example.com")
        secret_token = VerifyEmailTokenGenerator().make_token(user1)
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk + 1)),
                "secret_token": secret_token,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The email verification link you followed either has expired "
                "or is invalid. Please request another link to verify "
                "your email."
            ],
            "_main_code_": "invalid",
        }

        r2 = self.api_client.post(
            self.endpoint_confirm,
            data={
                "secret_token": secret_token,
            },
        )

        assert r2.status_code == 400
        assert r2.data == {
            "uidb64": [ErrorDetail(string="This field is required.", code="required")]
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    @pytest.mark.parametrize(
        "secret_token_case",
        ["session_but_missing", "incorrect"],
    )
    def test_verify_email_confirm_error_with_secret_token(
        self,
        key_variant: Literal["uidb_64", "uidb64"],
        secret_token_case: Literal["session_but_missing", "incorrect"],
    ):
        user1 = UserFactory.create(email="email1@example.com")
        secret_token = (
            VerifyEmailTokenGenerator().make_token(user1) + "_"
            if secret_token_case == "incorrect"
            else "verify-email"
        )
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "secret_token": secret_token,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The email verification link you followed either has expired "
                "or is invalid. Please request another link to verify "
                "your email."
            ],
            "_main_code_": "invalid",
        }

        r2 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
            },
        )

        assert r2.status_code == 400
        assert r2.data == {
            "secret_token": [
                ErrorDetail(string="This field is required.", code="required")
            ]
        }

    @pytest.mark.parametrize(
        "secret_token_variant", ["pulled_from_session", "set_explicitly"]
    )
    @pytest.mark.parametrize(
        "user_is_logged_in_while_confirming",
        [
            pytest.param(True, id="user_is_logged_in_while_confirming"),
            pytest.param(False, id="user_is_not_logged_in_while_confirming"),
        ],
    )
    def test_verify_email_confirm_full_flow(
        self,
        mailoutbox,
        secret_token_variant: Literal["pulled_from_session", "set_explicitly"],
        user_is_logged_in_while_confirming: bool,
    ):
        # Set up everything, and then post to the send endpoint to get the email sent.
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        client = APIClient()
        if user_is_logged_in_while_confirming:
            client.force_login(user1)

        sr1 = self.send(email=user1.email)

        # Extract the link from the email, and grab the necessary information for the
        # next steps.
        assert sr1.status_code == 200, "Pre-condition"
        assert len(mailoutbox) == 1, "Pre-condition"
        ea1 = EmailAssertions(mailoutbox[0])
        link = ea1.extract_verification_email_link()
        assert link, "Pre-condition"
        _, uidb64, secret_token = link.rsplit("/", 2)
        assert uidb64 and urlsafe_base64_encode(force_bytes(user1.pk)) == uidb64, (
            "Pre-condition"
        )
        assert secret_token and VerifyEmailTokenGenerator().check_token(
            user1, secret_token
        ), "Pre-condition"

        # Simulate the actual API flow that would happen when the user follows the link,
        # and then the frontend sends the request to the API.
        cr11 = Client.get(client, link, follow=False)
        next_link = cr11.headers["Location"]

        assert cr11.status_code == 302
        assert next_link != link
        assert next_link == f"/auth/verify-email/confirm/{uidb64}/verify-email"

        cr12 = Client.get(client, next_link, follow=False)

        assert cr12.status_code == 200
        initial_data = extract_initial_data(cr12)
        assert initial_data["extra"] == {
            "verifyEmailConfirm": {
                "isValid": True,
                "canRequestAnotherLink": True,
                "secretToken": "verify-email",
                "uidb64": uidb64,
            },
            "signaling": {
                "immediatelyRedirectTo": "verifyEmailConfirm",
            },
        }

        secret_token_for_confirm = (
            secret_token if secret_token_variant == "set_explicitly" else "verify-email"
        )

        cr2 = client.post(
            self.endpoint_confirm,
            data={"uidb64": uidb64, "secret_token": secret_token_for_confirm},
        )

        ur = cr2.wsgi_request
        user1.refresh_from_db()

        assert cr2.status_code == 200
        assert cr2.data == get_all_data(
            context=RequestContext(ur), request=ur, camel_case=False
        ) | {
            "csrf_token": IsStr(min_length=20),
        }

        assert user1.email_is_verified is True
        assert self.times.is_close_to_now(user1.email_verified_as_of)

        # Now that we've checked the success case, let's verify that re-following the
        # link and/or re-submitting to the confirm API endpoint fails. These links
        # should only be able to be used once, and we're confirming that with this part
        # of this test.

        client = APIClient()
        cr31 = Client.get(client, link, follow=False)
        next_link = cr31.headers["Location"]

        # The redirect should still continue as expected.
        assert cr31.status_code == 302
        assert next_link != link
        assert next_link == f"/auth/verify-email/confirm/{uidb64}/verify-email"

        cr32 = Client.get(client, next_link, follow=False)

        # We should land successfully on the frontend, but have `isValid` set to `False`
        # with `errorCode` and `errorMessage` set to the appropriate values. The
        # frontend will check for those and display a proper error page with proper
        # error message.
        assert cr32.status_code == 200
        initial_data = extract_initial_data(cr32)
        assert initial_data["extra"] == {
            "verifyEmailConfirm": {
                "isValid": False,
                "canRequestAnotherLink": True,
                "secretToken": "verify-email",
                "uidb64": uidb64,
                "errorCode": "invalid",
                "errorMessage": (
                    "The email verification link you followed either has expired or is "
                    "invalid. Please request another link to verify your email."
                ),
            },
            "signaling": {
                "immediatelyRedirectTo": "verifyEmailConfirm",
            },
        }

        cr4 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
            },
        )

        assert cr4.status_code == 400
        assert cr4.data == {
            "non_field_errors": [
                (
                    "The email verification link you followed either has expired or is "
                    "invalid. Please request another link to verify your email."
                )
            ],
            "_main_code_": "invalid",
        }


class TestChangePassword(BaseTestAuthViewSet):
    endpoint = "/api/auth/change-password"

    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    def post(self, **data: str):
        return self.api_client.post(self.endpoint, data=data)

    def test_user_not_authenticated(self):
        r = self.post()
        assert r.status_code == 403
        assert r.data == {"detail": "Authentication credentials were not provided."}

    def test_blank_new_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        self.api_client.force_login(user)

        r = self.post(
            previous_password=self.strong_password,
            new_password="",
            new_password_confirm="",
        )

        assert r.status_code == 400
        assert r.data == {
            "new_password": [
                ErrorDetail(string="This field may not be blank.", code="blank")
            ],
            "new_password_confirm": [
                ErrorDetail(string="This field may not be blank.", code="blank")
            ],
        }

    def test_invalid_new_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        self.api_client.force_login(user)
        previous_password = self.strong_password
        new_password = "password"

        r = self.post(
            previous_password=previous_password,
            new_password=new_password,
            new_password_confirm=new_password,
        )

        assert r.status_code == 400
        assert r.data == {
            "new_password": [
                ErrorDetail(
                    string="This password is too short. It must contain at least 9 characters.",
                    code="password_too_short",
                ),
                ErrorDetail(
                    string="This password is too common.", code="password_too_common"
                ),
                ErrorDetail(
                    string="Please include at least one number in your password",
                    code="password_missing_number",
                ),
                ErrorDetail(
                    string="Please include at least one special character (!@#$&*%?) in your password",
                    code="password_missing_special_character",
                ),
            ]
        }

    def test_passwords_do_not_match(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        self.api_client.force_login(user)
        previous_password = self.strong_password
        new_password = "Burn!IngSt@r542"

        r = self.post(
            previous_password=previous_password,
            new_password=new_password,
            new_password_confirm=new_password + "_",
        )

        assert r.status_code == 400
        assert r.data == {
            "new_password_confirm": [
                ErrorDetail(
                    string="Passwords do not match.",
                    code="invalid",
                )
            ]
        }

    def test_incorrect_previous_password(self):
        user1 = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        UserFactory.create(
            email="email2@example.com", password=self.strong_password + "_"
        )
        self.api_client.force_login(user1)
        previous_password = self.strong_password + "_"
        new_password = "Burn!IngSt@r542"

        r = self.post(
            previous_password=previous_password,
            new_password=new_password,
            new_password_confirm=new_password,
        )

        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": [
                "Incorrect password.",
            ],
            "_main_code_": "incorrect_password",
        }

    def test_successful(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        self.api_client.force_login(user)
        previous_password = self.strong_password
        new_password = "Burn!IngSt@r542"

        r = self.post(
            previous_password=previous_password,
            new_password=new_password,
            new_password_confirm=new_password,
        )

        user.refresh_from_db()

        ur = r.wsgi_request

        assert r.status_code == 200
        assert r.data == get_all_data(
            context=RequestContext(ur), request=ur, camel_case=False
        ) | {
            "csrf_token": IsStr(min_length=20),
        }

        assert user.check_password(new_password) is True
        assert user.check_password(previous_password) is False
        assert self.times.is_close_to_now(user.modified)


class TestResetPassword(BaseTestAuthViewSet):
    endpoint_begin = "/api/auth/reset-password/begin"
    endpoint_confirm = "/api/auth/reset-password/confirm"

    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    def begin(self, *, email: str, **kwargs: str):
        return self.api_client.post(
            self.endpoint_begin, data={"email": email, **kwargs}
        )

    def confirm(self, **data: str):
        return self.api_client.post(self.endpoint_confirm, data=data)

    def test_begin_error_invalid_email(self, mailoutbox):
        r1 = self.begin(email="invalid")
        assert r1.status_code == 400
        assert r1.data == {"email": ["Enter a valid email address."]}
        assert len(mailoutbox) == 0

    def test_begin_error_no_user(self, mailoutbox):
        UserFactory.create(email="email1@example.com", is_active=False)

        r1 = self.begin(email="email2@example.com")

        assert r1.status_code == 400
        assert r1.data == {
            "_main_code_": "no_user",
            "non_field_errors": [
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ],
        }

        assert len(mailoutbox) == 0

    def test_begin_error_inactive_user(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com", is_active=False)

        r1 = self.begin(email=user.email)

        assert r1.status_code == 400
        assert r1.data == {
            "_main_code_": "inactive",
            "non_field_errors": [
                "This account is inactive. Please contact support to reactivate it."
            ],
        }

    def test_begin_successful(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com")
        r1 = self.begin(email=user.email)

        assert r1.status_code == 200
        assert r1.data == {}

        assert len(mailoutbox) == 1
        ea1 = EmailAssertions(mailoutbox[0])
        ea1.assert_is_reset_password_email(to_email=user.email)
        link = ea1.extract_reset_password_email_link()
        assert link
        token = link.rsplit("/", 1)[1]
        assert PasswordResetTokenGenerator().check_token(user, token)

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    def test_reset_password_confirm_error_with_uidb64(
        self, key_variant: Literal["uidb_64", "uidb64"]
    ):
        user1 = UserFactory.create(email="email1@example.com")
        secret_token = PasswordResetTokenGenerator().make_token(user1)
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk + 1)),
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The reset password link you followed either has expired "
                "or is invalid. Please request another link to reset "
                "your password."
            ],
            "_main_code_": "invalid",
        }

        r2 = self.api_client.post(
            self.endpoint_confirm,
            data={
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r2.status_code == 400
        assert r2.data == {
            "uidb64": [ErrorDetail(string="This field is required.", code="required")]
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    @pytest.mark.parametrize(
        "secret_token_case",
        ["session_but_missing", "incorrect"],
    )
    def test_reset_password_confirm_error_with_secret_token(
        self,
        key_variant: Literal["uidb_64", "uidb64"],
        secret_token_case: Literal["session_but_missing", "incorrect"],
    ):
        user1 = UserFactory.create(email="email1@example.com")
        secret_token = (
            PasswordResetTokenGenerator().make_token(user1) + "_"
            if secret_token_case == "incorrect"
            else "reset-password"
        )
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "secret_token": secret_token,
                "password": self.strong_password,
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The reset password link you followed either has expired "
                "or is invalid. Please request another link to reset "
                "your password."
            ],
            "_main_code_": "invalid",
        }

        r2 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "password": self.strong_password,
            },
        )

        assert r2.status_code == 400
        assert r2.data == {
            "secret_token": [
                ErrorDetail(string="This field is required.", code="required")
            ]
        }

    @pytest.mark.parametrize("key_variant", ["uidb_64", "uidb64"])
    def test_reset_password_confirm_error_with_password(
        self, key_variant: Literal["uidb_64", "uidb64"]
    ):
        user1 = UserFactory.create(email="email1@example.com")
        secret_token = PasswordResetTokenGenerator().make_token(user1)
        r1 = self.api_client.post(
            self.endpoint_confirm,
            data={
                key_variant: urlsafe_base64_encode(force_bytes(user1.pk)),
                "secret_token": secret_token,
                "password": "password",
            },
        )

        assert r1.status_code == 400
        assert r1.data == {
            "password": [
                ErrorDetail(
                    string="This password is too short. It must contain at least 9 characters.",
                    code="password_too_short",
                ),
                ErrorDetail(
                    string="This password is too common.", code="password_too_common"
                ),
                ErrorDetail(
                    string="Please include at least one number in your password",
                    code="password_missing_number",
                ),
                ErrorDetail(
                    string="Please include at least one special character (!@#$&*%?) in your password",
                    code="password_missing_special_character",
                ),
            ]
        }

    @pytest.mark.parametrize(
        "secret_token_variant", ["pulled_from_session", "set_explicitly"]
    )
    @pytest.mark.parametrize(
        "user_is_logged_in_while_confirming",
        [
            pytest.param(True, id="user_is_logged_in_while_confirming"),
            pytest.param(False, id="user_is_not_logged_in_while_confirming"),
        ],
    )
    @pytest.mark.parametrize(
        "needs_email_verification",
        [
            pytest.param(True, id="needs_email_verification"),
            pytest.param(False, id="does_not_need_email_verification"),
        ],
    )
    def test_reset_password_confirm_full_flow(
        self,
        mailoutbox,
        secret_token_variant: str,
        user_is_logged_in_while_confirming: bool,
        needs_email_verification: bool,
    ):
        user_data: dict[str, Any] = {
            "email": "email1@example.com",
            "password": self.strong_password,
        }
        if needs_email_verification:
            user_data |= {
                "email_is_verified": False,
                "email_verified_as_of": None,
            }

        user1 = UserFactory.create(**user_data)
        client = APIClient()
        if user_is_logged_in_while_confirming:
            client.force_login(user1)

        r0 = self.begin(email=user1.email)

        # Extract the link from the email, and grab the necessary information for the
        # next steps.
        assert r0.status_code == 200, "Pre-condition"
        assert len(mailoutbox) == 1, "Pre-condition"
        ea1 = EmailAssertions(mailoutbox[0])
        link = ea1.extract_reset_password_email_link()
        assert link, "Pre-condition"
        _, uidb64, secret_token = link.rsplit("/", 2)
        assert uidb64 and urlsafe_base64_encode(force_bytes(user1.pk)) == uidb64, (
            "Pre-condition"
        )
        assert secret_token and PasswordResetTokenGenerator().check_token(
            user1, secret_token
        ), "Pre-condition"

        # Simulate the actual API flow that would happen when the user follows the link,
        # and then the frontend sends the request to the API.
        cr11 = Client.get(client, link, follow=False)
        next_link = cr11.headers["Location"]

        assert cr11.status_code == 302
        assert next_link != link
        assert next_link == f"/auth/reset-password/confirm/{uidb64}/set-password"

        cr12 = Client.get(client, next_link, follow=False)

        assert cr12.status_code == 200
        initial_data = extract_initial_data(cr12)
        assert initial_data["extra"] == {
            "resetPasswordConfirm": {
                "isValid": True,
                "canRequestAnotherLink": True,
                "secretToken": "set-password",
                "uidb64": uidb64,
            },
            "signaling": {
                "immediatelyRedirectTo": "resetPasswordConfirm",
            },
        }

        secret_token_for_confirm = (
            secret_token if secret_token_variant == "set_explicitly" else "set-password"
        )

        cr2 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
                "password": "Burn!IngSt@r542",
            },
        )

        ur = cr2.wsgi_request
        user1.refresh_from_db()

        assert cr2.status_code == 200
        assert cr2.data == get_all_data(
            context=RequestContext(ur), request=ur, camel_case=False
        ) | {
            "csrf_token": IsStr(min_length=20),
        }
        assert user1.check_password("Burn!IngSt@r542") is True
        assert self.times.is_close_to_now(user1.modified)

        assert user1.email_is_verified is True
        if needs_email_verification:
            assert self.times.is_close_to_now(user1.email_verified_as_of)

        # Now that we've checked the success case, let's verify that re-following the
        # link and/or re-submitting to the confirm API endpoint fails. These links
        # should only be able to be used once, and we're confirming that with this part
        # of this test.

        client = APIClient()
        cr31 = Client.get(client, link, follow=False)
        next_link = cr31.headers["Location"]

        # The redirect should still continue as expected.
        assert cr31.status_code == 302

        cr32 = Client.get(client, next_link, follow=False)

        # We should land successfully on the frontend, but have `isValid` set to `False`
        # with `errorCode` and `errorMessage` set to the appropriate values. The
        # frontend will check for those and display a proper error page with proper
        # error message.
        assert cr32.status_code == 200
        initial_data = extract_initial_data(cr32)

        assert initial_data["extra"]["signaling"] == {
            "immediatelyRedirectTo": "resetPasswordConfirm",
        }
        assert initial_data["extra"]["resetPasswordConfirm"] == {
            "secretToken": "set-password",
            "uidb64": uidb64,
            "isValid": False,
            "canRequestAnotherLink": True,
            "errorCode": "invalid",
            "errorMessage": (
                "The reset password link you followed either has expired or is "
                "invalid. Please request another link to reset your password."
            ),
        }

        cr4 = client.post(
            self.endpoint_confirm,
            data={
                "uidb64": uidb64,
                "secret_token": secret_token_for_confirm,
                "password": "Burn!IngSt@r543",
            },
        )

        assert cr4.status_code == 400
        assert cr4.data == {
            "non_field_errors": [
                (
                    "The reset password link you followed either has expired or is "
                    "invalid. Please request another link to reset your password."
                )
            ],
            "_main_code_": "invalid",
        }


class TestLogin(BaseTestAuthViewSet):
    endpoint = "/api/auth/login"
    strong_password = "Burn!IngSt@r541"

    def post(self, **data: str):
        data.setdefault("email", "email1@example.com")

        return self.api_client.post(self.endpoint, data=data)

    def test_login_success(self):
        user: User = UserFactory.create(
            email="email1@example.com",
            email_is_verified=True,
            name="email1@example.com",
            is_active=True,
        )
        user.set_password(self.strong_password)
        user.save()

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_login(user=user, assert_counter_equals=1):
            response = self.post(password=self.strong_password)

        user = User.objects.get()
        assert user.is_authenticated
        assert response.status_code == 200, "Current pre-condition"

        data = response.data
        assert data["user"] == get_user_data(user=user)
        assert data["session"] == {"is_authenticated": True}

    def test_login_empty_email(self):
        user: User = UserFactory.create(
            email="email1@example.com",
            email_is_verified=True,
            name="email1@example.com",
            is_active=True,
        )
        user.set_password(self.strong_password)
        user.save()

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_no_user_login(user=user, assert_counter_equals=1):
            r = self.post(email="", password=self.strong_password)

        assert r.status_code == 400
        assert r.data == {"email": ["This field may not be blank."]}

    def test_login_no_password(self):
        user: User = UserFactory.create(
            email="email1@example.com",
            email_is_verified=True,
            name="email1@example.com",
            is_active=True,
        )
        user.set_password(self.strong_password)
        user.save()

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_no_user_login(user=user, assert_counter_equals=1):
            r = self.post()

        assert r.status_code == 400
        assert r.data == {"password": ["This field is required."]}

    def test_login_incorrect_password(self):
        user: User = UserFactory.create(
            email="email1@example.com",
            email_is_verified=True,
            name="email1@example.com",
            is_active=True,
        )
        user.set_password(self.strong_password)
        user.save()

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_no_user_login(user=user, assert_counter_equals=1):
            r = self.post(password="OldPassword123!")

        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": ["Incorrect password."],
            "_main_code_": "incorrect_password",
        }


class TestLogout(BaseTestAuthViewSet):
    endpoint = "/api/auth/logout"

    def post(self, **data: str):
        return self.api_client.post(self.endpoint, data=data)

    def test_logout_success(self, user: User):
        self.api_client.force_login(user)

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_logout(user=user, assert_counter_equals=1):
            response = self.post()

        assert response.status_code == 200

        data = response.data
        data.pop("csrf_token")

        assert data == {
            "messages": [],
            "user": {"id": None, "is_authenticated": False},
            "memberships": [],
            "session": {"is_authenticated": False},
            "current_membership": None,
            "extra": {"signaling": {}},
        }

    def test_logout_already_logged_out(self, user: User):
        self.api_client.force_login(user)

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_logout(user=user, assert_counter_equals=1):
            self.post()

        with auth_watcher.expect_no_user_logout(user=user, assert_counter_equals=1):
            response = self.post()

        assert response.status_code == 200

        data = response.data
        data.pop("csrf_token")

        assert data == {
            "messages": [],
            "user": {"id": None, "is_authenticated": False},
            "memberships": [],
            "session": {"is_authenticated": False},
            "current_membership": None,
            "extra": {"signaling": {}},
        }
