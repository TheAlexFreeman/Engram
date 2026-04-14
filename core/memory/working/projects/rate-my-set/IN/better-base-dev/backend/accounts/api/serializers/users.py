from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Literal

from rest_framework import serializers

from backend.accounts.models import User
from backend.accounts.ops.users import (
    AutomatedPreDeleteActionType,
    CheckUserDeletionResult,
    ManualPreDeleteActionType,
    ManualPreDeleteWarningType,
)
from backend.utils.rest_framework.serializer_utils import exclude_fields

if TYPE_CHECKING:
    from .memberships import MembershipReadOnlyUserNotIncludedSerializer


class AnonymousUserReadOnlySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, read_only=True)
    is_authenticated = serializers.BooleanField(read_only=True)


class UserReadOnlySerializer(serializers.ModelSerializer[User]):
    is_authenticated = serializers.SerializerMethodField()

    def get_is_authenticated(self, obj: User) -> Literal[True]:
        return obj.is_authenticated

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "email_is_verified",
            "email_verified_as_of",
            "name",
            "uploaded_profile_image",
            "is_authenticated",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created",
        ]
        read_only_fields = fields


class UserUpdateSerializer(UserReadOnlySerializer):
    class Meta(UserReadOnlySerializer.Meta):
        fields = [*UserReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("name",), from_fields=fields)


class UserUpdateUploadedProfileImageSerializer(UserReadOnlySerializer):
    class Meta(UserReadOnlySerializer.Meta):
        fields = [*UserReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(
            ("uploaded_profile_image",), from_fields=fields
        )


class UserDeleteUploadedProfileImageSerializer(UserReadOnlySerializer):
    class Meta(UserReadOnlySerializer.Meta):
        fields = [*UserReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(
            ("uploaded_profile_image",), from_fields=fields
        )


class UserDestroySerializer(UserReadOnlySerializer):
    class Meta(UserReadOnlySerializer.Meta):
        fields = [*UserReadOnlySerializer.Meta.fields]
        read_only_fields = fields


class CheckUserDeletionSerializer(serializers.Serializer[CheckUserDeletionResult]):
    user = UserReadOnlySerializer(read_only=True)

    can_delete_user = serializers.SerializerMethodField()
    should_offer_manual_actions_before_deleting = serializers.SerializerMethodField()

    automated_actions_planned = serializers.SerializerMethodField()
    manual_actions_required = serializers.SerializerMethodField()
    manual_actions_offered = serializers.SerializerMethodField()
    account_ids_all_cleared = serializers.SerializerMethodField()

    def get_can_delete_user(self, obj: CheckUserDeletionResult) -> bool:
        return obj.can_delete_user

    def get_should_offer_manual_actions_before_deleting(
        self,
        obj: CheckUserDeletionResult,
    ) -> bool:
        return obj.should_offer_manual_actions_before_deleting

    def get_automated_actions_planned(
        self,
        obj: CheckUserDeletionResult,
    ) -> dict[int, AutomatedPreDeleteActionType]:
        return {k.id: v for k, v in obj.automated_actions_planned.items()}

    def get_manual_actions_required(
        self,
        obj: CheckUserDeletionResult,
    ) -> dict[int, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]]:
        return {k.id: v for k, v in obj.manual_actions_required.items()}

    def get_manual_actions_offered(
        self,
        obj: CheckUserDeletionResult,
    ) -> dict[int, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]]:
        return {k.id: v for k, v in obj.manual_actions_offered.items()}

    def get_account_ids_all_cleared(
        self,
        obj: CheckUserDeletionResult,
    ) -> list[int]:
        return [account.pk for account in obj.accounts_all_cleared]

    def __init__(self, *args, **kwargs):
        if "memberships" not in self._declared_fields:  # pragma: no cover
            self._declared_fields["memberships"] = (
                _get_check_user_deletion_memberships_serializer()
            )

        if hasattr(self, "Meta"):  # pragma: no cover
            if "memberships" not in self.Meta.fields:  # pragma: no cover
                self.Meta.fields = [
                    *[f for f in self.Meta.fields if f != "memberships"],
                    "memberships",
                ]

        super().__init__(*args, **kwargs)


@lru_cache(maxsize=1)
def _get_membership_read_only_user_not_included_serializer_class() -> type[
    MembershipReadOnlyUserNotIncludedSerializer
]:
    from .memberships import MembershipReadOnlyUserNotIncludedSerializer

    return MembershipReadOnlyUserNotIncludedSerializer


@lru_cache(maxsize=1)
def _get_check_user_deletion_memberships_serializer() -> (
    MembershipReadOnlyUserNotIncludedSerializer
):
    """
    Returns an instance of `MembershipReadOnlyUserNotIncludedSerializer` to be used in
    `memberships` within `CheckUserDeletionSerializer` (at the time of writing, may be
    used elsewhere as well in the future). This is here to resolve/solve circular import
    issues.
    """
    serializer_class = _get_membership_read_only_user_not_included_serializer_class()
    serializer = serializer_class(many=True, read_only=True)

    return serializer
