from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from rest_framework import serializers

from backend.accounts.models import Account
from backend.utils.rest_framework.serializer_utils import exclude_fields

if TYPE_CHECKING:
    from .memberships import MembershipReadOnlySerializer


class AccountReadOnlySerializer(serializers.ModelSerializer[Account]):
    account_type_display = serializers.SerializerMethodField()
    fallback_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    def get_account_type_display(self, obj: Account) -> str:
        return obj.get_account_type_display()

    def get_fallback_name(self, obj: Account) -> str:
        return obj.get_fallback_name(allow_db_query=False)

    def get_display_name(self, obj: Account) -> str:
        return obj.get_display_name(allow_db_query=False)

    class Meta:
        model = Account
        fields = [
            "id",
            "account_type",
            "account_type_display",
            "name",
            "uploaded_profile_image",
            "fallback_name",
            "display_name",
            "created",
        ]
        read_only_fields = fields


class AccountReadOnlyListSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = fields


class AccountCreateSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("account_type", "name"), from_fields=fields)

    def __init__(self, *args, **kwargs):
        if "membership_created" not in self._declared_fields:  # pragma: no cover
            self._declared_fields["membership_created"] = (
                _get_membership_created_serializer()
            )

        if "membership_created" not in self.Meta.fields:  # pragma: no cover
            self.Meta.fields = [
                *[f for f in self.Meta.fields if f != "membership_created"],
                "membership_created",
            ]

        super().__init__(*args, **kwargs)


class AccountUpdateSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("name",), from_fields=fields)


class AccountUpdateUploadedProfileImageSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(
            ("uploaded_profile_image",), from_fields=fields
        )


class AccountDeleteUploadedProfileImageSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(
            ("uploaded_profile_image",), from_fields=fields
        )


class AccountUpdateAccountTypeSerializer(AccountReadOnlySerializer):
    class Meta(AccountReadOnlySerializer.Meta):
        fields = [*AccountReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("account_type",), from_fields=fields)


@lru_cache(maxsize=1)
def _get_membership_created_serializer_class() -> type[MembershipReadOnlySerializer]:
    from .memberships import MembershipReadOnlySerializer

    return MembershipReadOnlySerializer


@lru_cache(maxsize=1)
def _get_membership_created_serializer() -> MembershipReadOnlySerializer:
    """
    Returns an instance of `MembershipReadOnlySerializer` to be used in
    `membership_created` within `AccountCreateSerializer` (at the time of writing, may
    be used elsewhere as well in the future). This is here to resolve/solve circular
    import issues.
    """
    serializer_class = _get_membership_created_serializer_class()
    serializer = serializer_class(source="membership_just_created", read_only=True)

    return serializer
