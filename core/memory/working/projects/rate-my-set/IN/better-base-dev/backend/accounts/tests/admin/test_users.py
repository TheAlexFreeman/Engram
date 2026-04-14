from __future__ import annotations

import pytest
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertInHTML
from pytest_subtests import SubTests

from backend.accounts.models import User
from backend.accounts.models.memberships import Membership
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom

pytestmark = pytest.mark.django_db


class TestUserAdmin:
    def test_changelist(self, admin_client):
        url = reverse("admin:accounts_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_search(self, admin_client):
        url = reverse("admin:accounts_user_changelist")
        response = admin_client.get(url, data={"q": "test"})
        assert response.status_code == 200

    def test_add_errors(self, admin_client, subtests: SubTests):
        a1 = AccountFactory.create()
        email1 = "some-test-email1@tests.betterbase.com"
        email1_case_insensitive = "some-TesT-Email1@tests.betterbase.com"
        email2 = "some-test-email2@tests.betterbase.com"
        assert email1 != email1_case_insensitive, "Pre-condition"
        assert email1.lower() == email1_case_insensitive.lower(), "Pre-condition"
        UserFactory.create(account=a1, email=email1)

        url = reverse("admin:accounts_user_add")

        with subtests.test(msg="Invalid: Need Owner if Account not specified"):
            get_response = admin_client.get(url)
            response = admin_client.post(
                url,
                data={
                    "email": email2,
                    "name": "Some Name",
                    "membership_role": str(Role.MEMBER),
                    "password1": "My_R@ndom-P@ssw0rd",
                    "password2": "My_R@ndom-P@ssw0rd",
                },
                follow=True,
            )

            assert get_response.status_code == 200
            assert response.status_code == 200

            assert not User.objects.filter(email__iexact=email2).exists()

            assertInHTML(
                (
                    "If you're leaving the Account blank so that it's automatically "
                    "created, you should keep the role set at the Owner default. "
                    "Otherwise, you can select whatever role."
                ),
                response.rendered_content,
                count=1,
            )

        with subtests.test(msg="Invalid: Email Already Taken (Case Insensitive)"):
            get_response = admin_client.get(url)
            response = admin_client.post(
                url,
                data={
                    "email": email1_case_insensitive,
                    "name": "Some Name",
                    "membership_role": str(Role.OWNER),
                    "password1": "My_R@ndom-P@ssw0rd",
                    "password2": "My_R@ndom-P@ssw0rd",
                },
                follow=True,
            )

            assert get_response.status_code == 200
            assert response.status_code == 200

            assert (
                User.objects.filter(
                    Q(email__iexact=email1) | Q(email__iexact=email1_case_insensitive)
                ).count()
                == 1
            )

            assertInHTML(
                f"This email has already been taken ({email1}).",
                response.rendered_content,
                count=1,
            )

        with subtests.test(msg="Invalid: Email Already Taken (Case Sensitive)"):
            get_response = admin_client.get(url)
            response = admin_client.post(
                url,
                data={
                    "email": email1,
                    "name": "Some Name",
                    "membership_role": str(Role.OWNER),
                    "password1": "My_R@ndom-P@ssw0rd",
                    "password2": "My_R@ndom-P@ssw0rd",
                },
                follow=True,
            )

            assert get_response.status_code == 200
            assert response.status_code == 200

            assert (
                User.objects.filter(
                    Q(email__iexact=email1) | Q(email__iexact=email1_case_insensitive)
                ).count()
                == 1
            )

            assertInHTML(
                f"This email has already been taken ({email1}).",
                response.rendered_content,
                count=1,
            )

    def test_add_success(self, admin_client, subtests: SubTests):
        a1 = AccountFactory.create()
        email1 = "some-test-email1@tests.betterbase.com"
        email2 = "some-test-email2@tests.betterbase.com"
        email3 = "some-test-email3@tests.betterbase.com"
        UserFactory.create(account=a1, email=email1)

        url = reverse("admin:accounts_user_add")

        with subtests.test(msg="Valid: No Account Specified"):
            start2 = timezone.now()
            get_response = admin_client.get(url)
            response = admin_client.post(
                url,
                data={
                    "email": email2,
                    "name": "Some Name 2",
                    "membership_role": str(Role.OWNER),
                    "password1": "My_R@ndom-P@ssw0rd",
                    "password2": "My_R@ndom-P@ssw0rd",
                },
                follow=True,
            )

            assert get_response.status_code == 200
            assert response.status_code == 200

            u2 = User.objects.get(email=email2)
            m2 = u2.active_memberships.get()
            a2 = m2.account

            assert u2.pk is not None
            assert u2.email == email2
            assert u2.name == "Some Name 2"
            assert u2.is_active is True
            assert u2.is_staff is False
            assert u2.is_superuser is False
            assert u2.date_joined >= start2
            assert u2.date_joined == u2.created
            assert u2.created_from == UserCreatedFrom.ADMIN
            assert u2.created >= start2
            assert u2.created == u2.date_joined
            assert u2.modified >= start2
            assert u2.modified == u2.date_joined
            assert u2.check_password("My_R@ndom-P@ssw0rd") is True
            assert m2.user == u2
            assert m2.role == Role.OWNER
            assert a2.pk is not None
            assert a2 != a1
            assert a2.pk == a1.pk + 1

        with subtests.test(msg="Valid: Account Specified"):
            start3 = timezone.now()
            get_response = admin_client.get(url)
            response = admin_client.post(
                url,
                data={
                    "account": str(a1.pk),
                    "email": email3,
                    "name": "Some Name 3",
                    "membership_role": str(Role.MEMBER),
                    "password1": "My_R@ndom-P@ssw0rd",
                    "password2": "My_R@ndom-P@ssw0rd",
                },
                follow=True,
            )

            assert get_response.status_code == 200
            assert response.status_code == 200

            u3 = User.objects.get(email=email3)
            m3 = u3.active_memberships.get()
            a3 = m3.account

            assert u3.pk is not None
            assert u3.email == email3
            assert u3.name == "Some Name 3"
            assert u3.is_active is True
            assert u3.is_staff is False
            assert u3.is_superuser is False
            assert u3.date_joined >= start3
            assert u3.date_joined == u3.created
            assert u3.created_from == UserCreatedFrom.ADMIN
            assert u3.created >= start3
            assert u3.created == u3.date_joined
            assert u3.modified >= start3
            assert u3.modified == u3.date_joined
            assert u3.check_password("My_R@ndom-P@ssw0rd") is True
            assert m3.user == u3
            assert m3.role == Role.MEMBER
            assert a3.pk is not None
            assert a3 == a1
            assert a3.pk == a1.pk

        assert (
            Membership.objects.filter(account__in=[a1, a2])
            .values_list("user")
            .distinct("user")
            .count()
        ) == 3

    def test_view_user(self, user, admin_client):
        user = User.objects.get(email=user.email)
        url = reverse("admin:accounts_user_change", kwargs={"object_id": user.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
