from __future__ import annotations

from functools import cached_property

from rest_framework import serializers
from rest_framework.request import Request

from backend.accounts.models import Membership, User
from backend.utils.rest_framework.serializer_utils import exclude_fields

from ...ops.memberships import (
    validate_can_delete_membership,
    validate_can_update_membership_role,
)
from .accounts import AccountReadOnlySerializer
from .users import UserReadOnlySerializer

MembershipAccountReadOnlySerializer = AccountReadOnlySerializer
MembershipUserReadOnlySerializer = UserReadOnlySerializer


class MembershipReadOnlySerializer(serializers.ModelSerializer[Membership]):
    account = MembershipAccountReadOnlySerializer(read_only=True)
    user = MembershipUserReadOnlySerializer(read_only=True)

    role_display = serializers.SerializerMethodField()

    def get_role_display(self, obj: Membership) -> str:
        return obj.get_role_display()

    class Meta:
        model = Membership
        fields = ["id", "account", "user", "role", "role_display", "created"]
        read_only_fields = fields


class MembershipReadOnlyAccountNotIncludedSerializer(MembershipReadOnlySerializer):
    class Meta(MembershipReadOnlySerializer.Meta):
        fields = exclude_fields(
            ("account",), from_fields=MembershipReadOnlySerializer.Meta.fields
        )
        read_only_fields = fields


class MembershipReadOnlyUserNotIncludedSerializer(MembershipReadOnlySerializer):
    class Meta(MembershipReadOnlySerializer.Meta):
        fields = exclude_fields(
            ("user",), from_fields=MembershipReadOnlySerializer.Meta.fields
        )
        read_only_fields = fields


class MembershipUpdateSerializerMixin(serializers.Serializer):
    default_error_messages = {
        "missing_initiating_membership": (
            "No membership found belonging to the same account as the membership being "
            "updated."
        )
    }

    @cached_property
    def authenticated_user(self) -> User:
        request: Request = self.context["request"]
        authenticated_user = request.user
        assert authenticated_user.is_authenticated and isinstance(
            authenticated_user, User
        ), "Pre-condition"
        return authenticated_user

    @cached_property
    def initiating_membership(self) -> Membership:
        instance = self.instance
        assert instance is not None and isinstance(instance, Membership), (
            "Pre-condition"
        )

        initiating_user = self.authenticated_user
        if (
            initiating_membership := initiating_user.get_membership_for_account_id(
                instance.account_id
            )
        ) is None:
            self.fail("missing_initiating_membership")
        return initiating_membership


class MembershipSelectSerializer(
    MembershipReadOnlySerializer, MembershipUpdateSerializerMixin
):
    default_error_messages = {
        "can_only_select_own_membership": (
            "Can only select a membership that is yours."
        )
    }

    class Meta(MembershipReadOnlySerializer.Meta):
        fields = [*MembershipReadOnlySerializer.Meta.fields, "last_selected_at"]
        read_only_fields = fields

    def validate(self, attrs):
        validated_data = super().validate(attrs)

        instance = self.instance
        assert instance is not None and isinstance(instance, Membership), (
            "Pre-condition"
        )
        initiating_membership = self.initiating_membership
        if instance != initiating_membership:
            self.fail("can_only_select_own_membership")

        return validated_data


class MembershipUpdateRoleSerializer(
    MembershipReadOnlySerializer, MembershipUpdateSerializerMixin
):
    class Meta(MembershipReadOnlySerializer.Meta):
        fields = [*MembershipReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("role",), from_fields=fields)

    def validate(self, attrs):
        instance = self.instance
        assert instance is not None and isinstance(instance, Membership), (
            "Pre-condition"
        )

        validated_data = super().validate(attrs)
        validated_data["from_role"] = instance.role
        validated_data["to_role"] = validated_data["role"]
        initiating_membership = self.initiating_membership

        validate_can_update_membership_role(
            instance,
            initiator=initiating_membership,
            from_role=validated_data["from_role"],
            to_role=validated_data["to_role"],
        )

        return validated_data


class MembershipDestroySerializer(
    MembershipReadOnlySerializer, MembershipUpdateSerializerMixin
):
    class Meta(MembershipReadOnlySerializer.Meta):
        pass

    def validate(self, attrs):
        instance = self.instance
        assert instance is not None and isinstance(instance, Membership), (
            "Pre-condition"
        )

        validated_data = super().validate(attrs)
        initiating_membership = self.initiating_membership

        validate_can_delete_membership(instance, initiator=initiating_membership)

        return validated_data
