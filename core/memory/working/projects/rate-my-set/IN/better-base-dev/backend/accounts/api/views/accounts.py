from __future__ import annotations

from functools import cached_property

from django.db.models import Exists, OuterRef
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet

from backend.accounts.api.permissions.accounts import (
    AccountMembershipOfRequestingUserIsOwner,
    AccountTypeMustBePersonal,
    RequestingUserHasMembershipInAccount,
)
from backend.accounts.models.users import User
from backend.accounts.ops.accounts import (
    delete_uploaded_profile_image as delete_uploaded_profile_image_op,
)
from backend.accounts.ops.accounts import (
    update_uploaded_profile_image as update_uploaded_profile_image_op,
)
from backend.accounts.ops.data_consistency import (
    check_account_and_membership_and_user_consistency_together,
)
from backend.accounts.ops.memberships import create_membership
from backend.accounts.ops.uploaded_images import (
    AccountUpdateUploadedProfileImageFailedResult,
    AccountUpdateUploadedProfileImageSuccessResult,
)
from backend.accounts.types.roles import Role
from backend.auth.api.permissions.verification import HasVerifiedEmail
from backend.utils.transactions import is_in_transaction

from ...models.accounts import Account, AccountType
from ...ops.accounts import (
    create_personal_account,
    create_team_account,
    update_account,
    update_account_type,
)
from ..serializers.accounts import (
    AccountCreateSerializer,
    AccountDeleteUploadedProfileImageSerializer,
    AccountReadOnlyListSerializer,
    AccountReadOnlySerializer,
    AccountUpdateAccountTypeSerializer,
    AccountUpdateSerializer,
    AccountUpdateUploadedProfileImageSerializer,
)


class AccountViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    read_only_serializer_class: type[BaseSerializer] = AccountReadOnlySerializer
    serializer_class = read_only_serializer_class
    queryset = Account.objects.all()
    permission_classes = [
        IsAuthenticated,
        HasVerifiedEmail,
        RequestingUserHasMembershipInAccount,
        AccountMembershipOfRequestingUserIsOwner,
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return AccountCreateSerializer
        if self.action == "list":
            return AccountReadOnlyListSerializer
        if self.action == "retrieve":
            return self.read_only_serializer_class
        if self.action in ("update", "partial_update"):
            return AccountUpdateSerializer
        if self.action == "update_account_type":
            return AccountUpdateAccountTypeSerializer
        if self.action == "update_uploaded_profile_image":
            return AccountUpdateUploadedProfileImageSerializer
        if self.action == "delete_uploaded_profile_image":
            return AccountDeleteUploadedProfileImageSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()

        # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
        if getattr(self, "swagger_fake_view", False):  # pragma: no cover
            return queryset

        # Restrict the queryset to accounts the request's user is a member of.
        return queryset.filter(
            Exists(self.user.active_memberships.filter(account_id=OuterRef("pk")))
        )

    def get_permissions(self):
        permission_classes = list(self.permission_classes)

        if self.action == "retrieve":
            if AccountMembershipOfRequestingUserIsOwner in permission_classes:
                permission_classes.remove(AccountMembershipOfRequestingUserIsOwner)
            if RequestingUserHasMembershipInAccount not in permission_classes:
                permission_classes.append(RequestingUserHasMembershipInAccount)

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer: AccountCreateSerializer) -> None:  # type: ignore[override]
        assert is_in_transaction(), "Pre-condition"

        validated_data = serializer.validated_data
        account_type = AccountType(validated_data["account_type"])

        account: Account
        if account_type == AccountType.PERSONAL:
            account = create_personal_account(name=validated_data["name"])
        elif account_type == AccountType.TEAM:
            account = create_team_account(name=validated_data["name"])
        else:
            raise RuntimeError(f'Unexpected/Unknown `account_type`: "{account_type}"')

        membership = create_membership(account=account, user=self.user, role=Role.OWNER)
        check_account_and_membership_and_user_consistency_together(
            account, membership, self.user
        )

        account.membership_just_created = membership

        serializer.instance = account

    def perform_update(self, serializer: AccountUpdateSerializer) -> None:  # type: ignore[override]
        account = serializer.instance
        assert account is not None and isinstance(account, Account), "Pre-condition"

        name = serializer.validated_data.get("name")
        if name:
            update_account(account, name=name)

    @action(
        detail=True,
        methods=["post"],
        url_path="update-account-type",
        url_name="update_account_type",
        permission_classes=[*permission_classes, AccountTypeMustBePersonal],
    )
    def update_account_type(self, request: Request, *args, **kwargs) -> Response:
        assert is_in_transaction(), "Pre-condition"

        account: Account = self.get_object()
        serializer = self.get_serializer(instance=account, data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        account_type = AccountType(validated_data["account_type"])

        update_account_type(account, new_account_type=account_type)

        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        url_path="update-uploaded-profile-image",
        url_name="update_uploaded_profile_image",
        methods=["post"],
    )
    def update_uploaded_profile_image(
        self, request: Request, *args, **kwargs
    ) -> Response:
        assert is_in_transaction(), "Pre-condition"

        account: Account = self.get_object()
        serializer = self.get_serializer(instance=account, data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = update_uploaded_profile_image_op(
            account, validated_data["uploaded_profile_image"]
        )
        if isinstance(result, AccountUpdateUploadedProfileImageFailedResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, AccountUpdateUploadedProfileImageSuccessResult), (
            "Post-condition"
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        url_path="delete-uploaded-profile-image",
        url_name="delete_uploaded_profile_image",
        methods=["post"],
    )
    def delete_uploaded_profile_image(
        self, request: Request, *args, **kwargs
    ) -> Response:
        assert is_in_transaction(), "Pre-condition"

        account: Account = self.get_object()
        serializer = self.get_serializer(instance=account, data=request.data)
        serializer.is_valid(raise_exception=True)
        delete_uploaded_profile_image_op(account)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @cached_property
    def user(self) -> User:
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"
        return user
