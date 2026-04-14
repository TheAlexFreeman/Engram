from __future__ import annotations

import random
from io import BytesIO
from typing import Any, Literal

import pytest
from django.test.client import Client
from rest_framework.exceptions import ErrorDetail
from rest_framework.test import APIClient

from backend.accounts.api.serializers.accounts import (
    AccountReadOnlyListSerializer,
    AccountReadOnlySerializer,
)
from backend.accounts.api.serializers.memberships import (
    MembershipReadOnlySerializer,
)
from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.memberships import Membership
from backend.accounts.tests.factories.memberships import MembershipFactory
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.images import create_test_image


@pytest.mark.django_db
class TestAccountViewSet:
    @pytest.fixture(autouse=True)
    def setup(
        self, times: Times, settings, client: Client, api_client: APIClient
    ) -> None:
        self.times = times
        self.settings = settings
        self.client = client
        self.api_client = api_client

    read_only_serializer_class: type[AccountReadOnlySerializer] = (
        AccountReadOnlySerializer
    )

    def test_create_personal_account(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.TEAM, membership__role=Role.OWNER
        )
        m1 = Membership.objects.get(user=u1)
        assert m1.user == u1, "Pre-condition"
        assert m1.role == Role.OWNER, "Pre-condition"
        assert m1.account.account_type == AccountType.TEAM, "Pre-condition"

        self.api_client.force_login(u1)
        response = self.api_client.post(
            "/api/accounts",
            data={
                "account_type": str(AccountType.PERSONAL),
                "name": "Personal Account 10",
            },
        )

        assert response.status_code == 201, response.data
        a2 = Account.objects.exclude(id=m1.account_id).get()
        assert a2.account_type == AccountType.PERSONAL, "Post-condition"
        assert a2.name == "Personal Account 10", "Post-condition"
        m2 = Membership.objects.get(user=u1, account=a2)
        assert m2.user == u1, "Post-condition"
        assert m2.role == Role.OWNER, "Post-condition"
        assert m2.account == a2, "Post-condition"
        m2_serialized = MembershipReadOnlySerializer(m2).data
        self._assert_response(
            response,
            status_code=201,
            account=a2,
            extra_data={"membership_created": m2_serialized},
        )

    def test_create_team_account(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.get(user=u1)
        assert m1.user == u1, "Pre-condition"
        assert m1.role == Role.OWNER, "Pre-condition"
        assert m1.account.account_type == AccountType.PERSONAL, "Pre-condition"

        self.api_client.force_login(u1)
        response = self.api_client.post(
            "/api/accounts",
            data={"account_type": str(AccountType.TEAM), "name": "Team Account 10"},
        )

        assert response.status_code == 201, response.data
        a2 = Account.objects.exclude(id=m1.account_id).get()
        assert a2.account_type == AccountType.TEAM, "Post-condition"
        assert a2.name == "Team Account 10", "Post-condition"
        m2 = Membership.objects.get(user=u1, account=a2)
        assert m2.user == u1, "Post-condition"
        assert m2.role == Role.OWNER, "Post-condition"
        assert m2.account == a2, "Post-condition"
        m2_serialized = MembershipReadOnlySerializer(m2).data
        self._assert_response(
            response,
            status_code=201,
            account=a2,
            extra_data={"membership_created": m2_serialized},
        )

    def test_create_account_invalid(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        self.api_client.force_login(u1)

        u1.email_is_verified = False
        u1.email_verified_as_of = None
        u1.save(update_fields=["email_is_verified", "email_verified_as_of", "modified"])

        response_email_not_verified = self.api_client.post(
            "/api/accounts",
            data={"account_type": str(AccountType.TEAM), "name": "Team Account 1"},
        )
        assert response_email_not_verified.status_code == 403, (
            response_email_not_verified.data
        )
        assert response_email_not_verified.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )

        u1.email_is_verified = True
        u1.email_verified_as_of = self.times.now
        u1.save(update_fields=["email_is_verified", "email_verified_as_of", "modified"])

        response_invalid_account_type = self.api_client.post(
            "/api/accounts",
            data={"account_type": "Goosey Goose", "name": "Account 1"},
        )
        assert response_invalid_account_type.status_code == 400, (
            response_invalid_account_type.data
        )
        assert response_invalid_account_type.data["account_type"] == [
            ErrorDetail('"Goosey Goose" is not a valid choice.', code="invalid_choice")
        ]

    def test_list_accounts(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account

        m2 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=AccountType.TEAM
        )
        a2 = m2.account
        m3 = MembershipFactory.create(
            user=u1, role=Role.MEMBER, account__account_type=AccountType.TEAM
        )
        a3 = m3.account
        m4 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=AccountType.PERSONAL
        )
        a4 = m4.account
        m5 = MembershipFactory.create(
            user=u1, role=Role.MEMBER, account__account_type=AccountType.PERSONAL
        )
        a5 = m5.account

        u2 = UserFactory.create()
        m6 = MembershipFactory.create(user=u2, account__account_type=AccountType.TEAM)
        a6 = m6.account  # noqa: F841
        m7 = MembershipFactory.create(user=u2, account__account_type=AccountType.TEAM)
        a7 = m7.account  # noqa: F841
        m8 = MembershipFactory.create(
            user=u2, account__account_type=AccountType.PERSONAL
        )
        a8 = m8.account  # noqa: F841
        m9 = MembershipFactory.create(
            user=u2, account__account_type=AccountType.PERSONAL
        )
        a9 = m9.account  # noqa: F841

        self.api_client.force_login(u1)
        response = self.api_client.get("/api/accounts")

        assert response.status_code == 200, response.data
        data = response.data
        assert len(data) == 5
        assert {i["id"]: i for i in data} == {
            a1.id: AccountReadOnlyListSerializer(a1).data,
            a2.id: AccountReadOnlyListSerializer(a2).data,
            a3.id: AccountReadOnlyListSerializer(a3).data,
            a4.id: AccountReadOnlyListSerializer(a4).data,
            a5.id: AccountReadOnlyListSerializer(a5).data,
        }

    def test_retrieve_account(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account

        m2 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=AccountType.TEAM
        )
        a2 = m2.account
        m3 = MembershipFactory.create(
            user=u1, role=Role.MEMBER, account__account_type=AccountType.TEAM
        )
        a3 = m3.account

        u2 = UserFactory.create()
        m4 = MembershipFactory.create(user=u2, account__account_type=AccountType.TEAM)
        a4 = m4.account
        m5 = MembershipFactory.create(user=u2, account__account_type=AccountType.TEAM)
        a5 = m5.account

        self.api_client.force_login(u1)

        r1 = self.api_client.get(f"/api/accounts/{a1.id}")
        assert r1.status_code == 200, r1.data
        assert r1.data == AccountReadOnlySerializer(a1).data

        r2 = self.api_client.get(f"/api/accounts/{a2.id}")
        assert r2.status_code == 200, r2.data
        assert r2.data == AccountReadOnlySerializer(a2).data

        r3 = self.api_client.get(f"/api/accounts/{a3.id}")
        assert r3.status_code == 200, r3.data
        assert r3.data == AccountReadOnlySerializer(a3).data

        r4 = self.api_client.get(f"/api/accounts/{a4.id}")
        assert r4.status_code == 404, r4.data

        r5 = self.api_client.get(f"/api/accounts/{a5.id}")
        assert r5.status_code == 404, r5.data

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_update_account(self, account_type: AccountType):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account  # noqa: F841

        m2 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=account_type
        )
        a2 = m2.account

        other_account_type = random.choice(
            [V for V in AccountType if V != account_type]
        )

        self.api_client.force_login(u1)

        r1 = self.api_client.put(
            f"/api/accounts/{a2.id}", data={"name": "Some Other Name"}
        )

        a2.refresh_from_db()
        assert r1.status_code == 200
        assert r1.data == AccountReadOnlySerializer(a2).data
        assert a2.account_type == account_type
        assert a2.name == "Some Other Name"

        r2 = self.api_client.put(
            f"/api/accounts/{a2.id}",
            data={
                "account_type": other_account_type,
                "name": "Some Other Name 2",
            },
        )

        a2.refresh_from_db()
        assert r2.status_code == 200
        assert r2.data == AccountReadOnlySerializer(a2).data
        assert a2.account_type == account_type
        assert a2.name == "Some Other Name 2"

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_partial_update_account(self, account_type: AccountType):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account  # noqa: F841

        m2 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=account_type
        )
        a2 = m2.account

        other_account_type = random.choice(
            [V for V in AccountType if V != account_type]
        )

        self.api_client.force_login(u1)

        r1 = self.api_client.patch(
            f"/api/accounts/{a2.id}", data={"name": "Some Other Name"}
        )

        a2.refresh_from_db()
        assert r1.status_code == 200
        assert r1.data == AccountReadOnlySerializer(a2).data
        assert a2.account_type == account_type
        assert a2.name == "Some Other Name"

        r2 = self.api_client.patch(
            f"/api/accounts/{a2.id}",
            data={
                "account_type": other_account_type,
                "name": "Some Other Name 2",
            },
        )

        a2.refresh_from_db()
        assert r2.status_code == 200
        assert r2.data == AccountReadOnlySerializer(a2).data
        assert a2.account_type == account_type
        assert a2.name == "Some Other Name 2"

    @pytest.mark.parametrize("account_type", [*AccountType])
    @pytest.mark.parametrize("http_method", ["PUT", "PATCH"])
    def test_update_account_invalid(
        self,
        account_type: AccountType,
        http_method: Literal["PUT", "PATCH"],
    ):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account

        m2 = MembershipFactory.create(
            user=u1, role=Role.OWNER, account__account_type=account_type
        )
        a2 = m2.account
        m3 = MembershipFactory.create(
            user=u1, role=Role.MEMBER, account__account_type=account_type
        )
        a3 = m3.account

        u2 = UserFactory.create()
        m4 = MembershipFactory.create(
            user=u2, account__account_type=AccountType.PERSONAL
        )
        a4 = m4.account
        m5 = MembershipFactory.create(user=u2, account__account_type=AccountType.TEAM)
        a5 = m5.account

        u1.email_is_verified = False
        u1.email_verified_as_of = None
        u1.save(update_fields=["email_is_verified", "email_verified_as_of", "modified"])

        self.api_client.force_login(u1)
        method = self.api_client.put if http_method == "PUT" else self.api_client.patch

        r11 = method(f"/api/accounts/{a1.id}", data={"name": "Other Account Name 1"})
        r12 = method(f"/api/accounts/{a2.id}", data={"name": "Other Account Name 1"})
        r13 = method(f"/api/accounts/{a3.id}", data={"name": "Other Account Name 1"})
        r14 = method(f"/api/accounts/{a4.id}", data={"name": "Other Account Name 1"})
        r15 = method(f"/api/accounts/{a5.id}", data={"name": "Other Account Name 1"})

        assert r11.status_code == 403
        assert r11.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )
        assert r12.status_code == 403
        assert r12.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )
        assert r13.status_code == 403
        assert r13.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )
        assert r14.status_code == 403
        assert r14.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )
        assert r15.status_code == 403
        assert r15.data["detail"] == ErrorDetail(
            "You must verify your email before you can perform this action.",
            code="email_not_verified",
        )

        u1.email_is_verified = True
        u1.email_verified_as_of = self.times.now
        u1.save(update_fields=["email_is_verified", "email_verified_as_of", "modified"])

        r21 = method(f"/api/accounts/{a1.id}", data={"name": "Other Account Name 1"})
        r22 = method(f"/api/accounts/{a2.id}", data={"name": "Other Account Name 1"})
        r23 = method(f"/api/accounts/{a3.id}", data={"name": "Other Account Name 1"})
        r24 = method(f"/api/accounts/{a4.id}", data={"name": "Other Account Name 1"})
        r25 = method(f"/api/accounts/{a5.id}", data={"name": "Other Account Name 1"})

        assert r21.status_code == 200
        assert r22.status_code == 200
        assert r23.status_code == 403
        assert r23.data["detail"] == ErrorDetail(
            "You must be an owner role in the account to perform this action.",
            code="account_membership_of_requesting_user_is_not_owner",
        )
        assert r24.status_code == 404
        assert r25.status_code == 404

    def test_update_account_type_from_personal_to_team(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account
        assert a1.account_type == AccountType.PERSONAL, "Pre-condition"

        self.api_client.force_login(u1)

        r1 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-account-type",
            data={"account_type": str(AccountType.TEAM)},
        )
        assert r1.status_code == 200
        a1.refresh_from_db()
        assert r1.data == AccountReadOnlySerializer(a1).data
        assert a1.account_type == AccountType.TEAM

    def test_update_account_type_from_team_to_personal(self):
        u1 = UserFactory.create(
            account__account_type=AccountType.TEAM, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account
        assert a1.account_type == AccountType.TEAM, "Pre-condition"

        self.api_client.force_login(u1)

        r1 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-account-type",
            data={"account_type": str(AccountType.PERSONAL)},
        )
        assert r1.status_code == 403
        assert r1.data["detail"] == ErrorDetail(
            "You can only perform this action if the account you're performing it on is a personal account.",
            code="account_type_is_not_personal",
        )

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_update_uploaded_profile_image(self, account_type: AccountType):
        u1 = UserFactory.create(
            account__account_type=account_type, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account
        assert a1.account_type == account_type, "Pre-condition"
        assert not a1.uploaded_profile_image, "Current pre-condition"

        self.api_client.force_login(u1)

        test_image1 = self._make_test_image(
            "some-test-image1.jpg", r=101, g=102, b=103, x_size=256, y_size=256
        )

        r1 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-uploaded-profile-image",
            data={"uploaded_profile_image": test_image1},
            format="multipart",
        )
        test_image1.seek(0)

        assert r1.status_code == 200, r1.data
        a1.refresh_from_db()
        a1_data = AccountReadOnlySerializer(a1).data
        uploaded_profile_image1 = a1.uploaded_profile_image
        assert uploaded_profile_image1
        assert uploaded_profile_image1.name is not None
        assert uploaded_profile_image1.path is not None
        assert uploaded_profile_image1.url is not None
        assert "some-test-image1.jpg" in uploaded_profile_image1.name
        assert "some-test-image1.jpg" in uploaded_profile_image1.path
        assert "some-test-image1.jpg" in uploaded_profile_image1.url
        assert uploaded_profile_image1.read() == test_image1.read()
        assert r1.data == {
            **a1_data,
            "uploaded_profile_image": f"http://testserver{a1_data['uploaded_profile_image']}",
        }

        # Now, make sure we can update with a different image as well, given there's an
        # existing one.

        test_image2 = self._make_test_image(
            "some-test-image2.jpg", r=104, g=105, b=106, x_size=256, y_size=256
        )

        r2 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-uploaded-profile-image",
            data={"uploaded_profile_image": test_image2},
            format="multipart",
        )
        test_image2.seek(0)
        test_image1.seek(0)

        assert r2.status_code == 200, r2.data
        a1.refresh_from_db()
        a1_data = AccountReadOnlySerializer(a1).data
        uploaded_profile_image2 = a1.uploaded_profile_image
        assert uploaded_profile_image2
        assert uploaded_profile_image2.name is not None
        assert uploaded_profile_image2.path is not None
        assert uploaded_profile_image2.url is not None
        assert "some-test-image2.jpg" in uploaded_profile_image2.name
        assert "some-test-image2.jpg" in uploaded_profile_image2.path
        assert "some-test-image2.jpg" in uploaded_profile_image2.url
        assert uploaded_profile_image2.read() == test_image2.read()
        assert uploaded_profile_image2.read() != test_image1.read()
        assert r2.data == {
            **a1_data,
            "uploaded_profile_image": f"http://testserver{a1_data['uploaded_profile_image']}",
        }

        test_image3 = self._make_test_image(
            "some-test-image3.jpg", r=109, g=110, b=111, x_size=1_025, y_size=1_025
        )

        # Finally, check at least one error. Operations tests cover the rest of the
        # errors.
        r3 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-uploaded-profile-image",
            data={"uploaded_profile_image": test_image3},
            format="multipart",
        )
        assert r3.status_code == 400, r3.data

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_delete_uploaded_profile_image(self, account_type: AccountType):
        u1 = UserFactory.create(
            account__account_type=account_type, membership__role=Role.OWNER
        )
        m1 = Membership.objects.select_related("account").get(user=u1)
        a1 = m1.account
        assert a1.account_type == account_type, "Pre-condition"
        assert not a1.uploaded_profile_image, "Current pre-condition"

        self.api_client.force_login(u1)

        test_image1 = self._make_test_image(
            "some-test-image1.jpg", r=101, g=102, b=103, x_size=256, y_size=256
        )

        r1 = self.api_client.post(
            f"/api/accounts/{a1.id}/update-uploaded-profile-image",
            data={"uploaded_profile_image": test_image1},
            format="multipart",
        )
        test_image1.seek(0)

        assert r1.status_code == 200, r1.data
        a1.refresh_from_db()
        a1_data = AccountReadOnlySerializer(a1).data
        uploaded_profile_image = a1.uploaded_profile_image
        assert uploaded_profile_image
        assert uploaded_profile_image.name is not None
        assert uploaded_profile_image.path is not None
        assert uploaded_profile_image.url is not None
        assert "some-test-image1.jpg" in uploaded_profile_image.name
        assert "some-test-image1.jpg" in uploaded_profile_image.path
        assert "some-test-image1.jpg" in uploaded_profile_image.url
        assert uploaded_profile_image.read() == test_image1.read()
        assert r1.data == {
            **a1_data,
            "uploaded_profile_image": f"http://testserver{a1_data['uploaded_profile_image']}",
        }

        test_image1.close()
        a1.uploaded_profile_image.close()

        r2 = self.api_client.post(
            f"/api/accounts/{a1.id}/delete-uploaded-profile-image",
        )
        assert r2.status_code == 200, r2.data
        a1.refresh_from_db()
        assert not a1.uploaded_profile_image
        assert r2.data == {
            **a1_data,
            "uploaded_profile_image": None,
        }

        r3 = self.api_client.post(
            f"/api/accounts/{a1.id}/delete-uploaded-profile-image",
        )
        assert r3.status_code == 200, r3.data
        a1.refresh_from_db()
        assert not a1.uploaded_profile_image
        assert r3.data == {
            **a1_data,
            "uploaded_profile_image": None,
        }

    def _assert_response(
        self,
        response: Any,
        data: Any = "default",
        status_code: int = 200,
        account: Account | None = None,
        refresh_from_db: bool = False,
        extra_data: dict[str, Any] | None = None,
    ):
        if account is not None and refresh_from_db:
            account.refresh_from_db()

        if data == "default":
            assert account is not None, (
                'If `data == "default"` then `account` must be provided.'
            )
            data = self.read_only_serializer_class(account).data

        if extra_data is not None:
            data.update(extra_data)

        assert response.status_code == status_code
        assert response.data == data

    def _make_test_image(
        self,
        filename: str,
        *,
        r: int | None = None,
        g: int | None = None,
        b: int | None = None,
        x_size: int = 128,
        y_size: int = 128,
    ) -> BytesIO:
        image_file = create_test_image(
            filename, r=r, g=g, b=b, size_x=x_size, size_y=y_size
        )
        image_file.seek(0)
        assert image_file, "Pre-condition"

        bytes_io_instance = BytesIO(image_file.read())
        bytes_io_instance.name = filename
        bytes_io_instance.seek(0)
        assert bytes_io_instance, "Pre-condition"

        image_file.close()

        return bytes_io_instance
