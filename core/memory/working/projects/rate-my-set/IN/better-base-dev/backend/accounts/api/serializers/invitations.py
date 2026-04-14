from __future__ import annotations

from functools import cached_property
from typing import Any, cast

from django_stubs_ext import StrOrPromise
from rest_framework import serializers
from rest_framework.request import Request

from backend.accounts.api.serializers.accounts import AccountReadOnlySerializer
from backend.accounts.api.serializers.users import UserReadOnlySerializer
from backend.accounts.models import Invitation
from backend.accounts.types.invitations import DeliveryMethod
from backend.utils.rest_framework.exception_reraising import (
    reraise_as_permission_denied,
)
from backend.utils.rest_framework.fields import (
    ModelAttributeReadHiddenField,
    WritePrimaryKeyReadSerializerRelatedField,
)
from backend.utils.rest_framework.serializer_utils import exclude_fields

from ...models.accounts import Account, AccountType
from ...models.users import User
from ...ops.invitations import (
    CanAcceptResult,
    CanDeclineResult,
    validate_can_accept_invitation,
    validate_can_create_invitation,
    validate_can_decline_invitation,
    validate_can_delete_invitation,
    validate_can_resend_invitation,
    validate_can_update_invitation,
)


class InvitationReadOnlySerializer(serializers.ModelSerializer[Invitation]):
    account = AccountReadOnlySerializer(read_only=True)
    invited_by = UserReadOnlySerializer(read_only=True)
    user = UserReadOnlySerializer(read_only=True)

    role_display = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    is_declined = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_past_follow_window = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    team_display_name = serializers.SerializerMethodField()
    is_using_fallback_team_display_name = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()

    def get_role_display(self, obj: Invitation) -> str:
        return obj.get_role_display()

    def get_is_accepted(self, obj: Invitation) -> bool:
        return obj.is_accepted

    def get_is_declined(self, obj: Invitation) -> bool:
        return obj.is_declined

    def get_is_expired(self, obj: Invitation) -> bool:
        return obj.is_expired

    def get_is_past_follow_window(self, obj: Invitation) -> bool:
        return obj.is_past_follow_window

    def get_status(self, obj: Invitation) -> str:
        return str(obj.status)

    def get_status_display(self, obj: Invitation) -> StrOrPromise:
        return obj.status.label

    # Make `str` instead of `StrOrPromise` so that `drf_spectacular` can better infer a
    # string type without throwing a warning/error.
    def get_team_display_name(self, obj: Invitation) -> str:
        return cast(str, obj.team_display_name)

    def get_is_using_fallback_team_display_name(self, obj: Invitation) -> bool:
        return obj.is_using_fallback_team_display_name

    # Make `str` instead of `StrOrPromise` so that `drf_spectacular` can better infer a
    # string type without throwing a warning/error.
    def get_headline(self, obj: Invitation) -> str:
        return cast(str, obj.headline)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "account",
            "invited_by",
            "email",
            "name",
            "role",
            "role_display",
            "user",
            "accepted_at",
            "expires_at",
            "delivery_method",
            "last_sent_at",
            "created",
            "is_accepted",
            "is_declined",
            "is_expired",
            "is_past_follow_window",
            "status",
            "status_display",
            "team_display_name",
            "is_using_fallback_team_display_name",
            "headline",
        ]
        read_only_fields = fields


class InvitationListReadOnlySerializer(InvitationReadOnlySerializer):
    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = fields


class InvitationListUserExcludedReadOnlySerializer(InvitationListReadOnlySerializer):
    class Meta(InvitationListReadOnlySerializer.Meta):
        fields = exclude_fields(
            ("user",), from_fields=InvitationListReadOnlySerializer.Meta.fields
        )
        read_only_fields = fields


class InvitationListAccountExcludedReadOnlySerializer(InvitationListReadOnlySerializer):
    class Meta(InvitationListReadOnlySerializer.Meta):
        fields = exclude_fields(
            ("account",), from_fields=InvitationListReadOnlySerializer.Meta.fields
        )
        read_only_fields = fields


class InvitationCreateSerializer(InvitationReadOnlySerializer):
    default_error_messages = {
        "missing_membership": "You are not a member of this account.",
        "not_team_account": (
            "The account you're attempting to invite to is not a team account. Please "
            "create a team account first and then invite members to that account."
        ),
        "wrong_invited_by": "You cannot invite a member on behalf of another account.",
    }

    account = WritePrimaryKeyReadSerializerRelatedField(  # type: ignore[assignment]
        queryset=Account.objects.all(),
        deserialize=AccountReadOnlySerializer(read_only=True),
    )
    invited_by = ModelAttributeReadHiddenField(  # type: ignore[assignment]
        default=serializers.CurrentUserDefault(),
        deserialize=UserReadOnlySerializer(read_only=True),
    )

    # NOTE: `reraise_as_permission_denied` is here to make some 400s be raised as 403s
    # to keep consistency with update, resend, and other actions. Easier to put some
    # permissions-related checks in the serializer here because we will have fully
    # resolved the raw provided data and validated it, pulled I.E. the `Account` from
    # the DB first, etc., so then we can check permissions.
    @reraise_as_permission_denied(
        codes_set={"missing_membership", "owner_required", "wrong_invited_by"}
    )
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)
        account: Account = validated_data["account"]
        invited_by: User = validated_data["invited_by"]

        if account.account_type != AccountType.TEAM:
            self.fail("not_team_account")

        if (membership := invited_by.get_membership_for_account_id(account.pk)) is None:
            self.fail("missing_membership")

        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        # NOTE: At the time of writing, because `invited_by` defaults to
        # `serializers.CurrentUserDefault()` and is a hidden field, this `if` branch
        # should never be entered in practice. Hence, consider this just more of a
        # defensive programming measure.
        if user != invited_by:  # pragma: no cover
            self.fail("wrong_invited_by")

        validate_can_create_invitation(
            initiator=membership, email=validated_data["email"]
        )

        validated_data["invited_by"] = invited_by
        return validated_data

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(
            ("account", "invited_by", "email", "name", "role", "delivery_method"),
            from_fields=fields,
        )
        extra_kwargs = {"delivery_method": {"default": DeliveryMethod.EMAIL}}


class InvitationUpdateSerializer(InvitationReadOnlySerializer):
    default_error_messages = {
        "missing_membership": InvitationCreateSerializer.default_error_messages[
            "missing_membership"
        ]
    }

    def validate(self, attrs: dict[str, Any]):
        validated_data = super().validate(attrs)
        invitation = self.instance
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )

        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            membership := user.get_membership_for_account_id(invitation.account_id)
        ) is None:
            self.fail("missing_membership")

        validate_can_update_invitation(invitation, initiator=membership)

        return validated_data

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = exclude_fields(("name", "role"), from_fields=fields)


class InvitationResendSerializer(InvitationReadOnlySerializer):
    default_error_messages = {
        "missing_membership": InvitationCreateSerializer.default_error_messages[
            "missing_membership"
        ]
    }

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = fields

    def validate(self, attrs: dict[str, Any]):
        validated_data = super().validate(attrs)
        invitation = self.instance
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )

        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            membership := user.get_membership_for_account_id(invitation.account_id)
        ) is None:
            self.fail("missing_membership")

        validate_can_resend_invitation(invitation, initiator=membership)

        return validated_data


class InvitationAcceptSerializer(InvitationReadOnlySerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        # Make linters/type checkers happy and make sure `self.can_accept_result` is
        # accessed in the validation phase here.
        result = self.can_accept_result
        if not isinstance(result, CanAcceptResult):
            raise RuntimeError(
                "`result` should be an instance of `CanAcceptResult` and we need to "
                "access to trigger validation and allow outside code to access the "
                "result."
            )

        validated_data["can_accept_result"] = result

        return validated_data

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = fields

    @cached_property
    def can_accept_result(self) -> CanAcceptResult:
        invitation = self.instance
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )
        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return validate_can_accept_invitation(
            invitation,
            initiator=user,
            request=request._request,
            is_special_pre_user_creation_case=False,
        )


class InvitationDeclineSerializer(InvitationReadOnlySerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        # Make linters/type checkers happy and make sure `self.can_accept_result` is
        # accessed in the validation phase here.
        result = self.can_decline_result
        if not isinstance(result, CanDeclineResult):
            raise RuntimeError(
                "`result` should be an instance of `CanDeclineResult` and we need to "
                "access to trigger validation and allow outside code to access the "
                "result."
            )

        validated_data["can_decline_result"] = result

        return validated_data

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = fields

    @cached_property
    def can_decline_result(self) -> CanDeclineResult:
        invitation = self.instance
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )
        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return validate_can_decline_invitation(
            invitation,
            initiator=user,
            request=request._request,
            is_special_pre_user_creation_case=False,
        )


class InvitationDeleteSerializer(InvitationReadOnlySerializer):
    default_error_messages = {
        "missing_membership": InvitationCreateSerializer.default_error_messages[
            "missing_membership"
        ]
    }

    def validate(self, attrs: dict[str, Any]):
        validated_data = super().validate(attrs)
        invitation = self.instance
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )

        request: Request = self.context["request"]
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            membership := user.get_membership_for_account_id(invitation.account_id)
        ) is None:
            self.fail("missing_membership")

        validate_can_delete_invitation(invitation, initiator=membership)

        return validated_data

    class Meta(InvitationReadOnlySerializer.Meta):
        fields = [*InvitationReadOnlySerializer.Meta.fields]
        read_only_fields = fields
