from __future__ import annotations

from functools import cached_property
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise
from rest_framework import serializers
from rest_framework.request import Request

from backend.accounts.models.invitations import Invitation
from backend.accounts.models.users import User
from backend.accounts.ops.invitations import (
    CanAcceptResult,
    ExpandedSessionFollowedInvitation,
    construct_temporary_pre_persisted_user_for_acceptance_validation,
    get_invitations_followed_from_session,
    validate_can_accept_invitation,
)
from backend.auth.models.email_changes import EmailChangeRequest


class RefreshMeSerializer(serializers.Serializer):
    pass


class LoginSerializer(serializers.Serializer):
    """
    Just check that some `email` and `password` are provided (and
    non-blank/empty/null/etc.).
    """

    email = serializers.EmailField()
    password = serializers.CharField(max_length=255)


class LoginFromInvitationSerializer(LoginSerializer):
    invitation_id = serializers.IntegerField()


class LoginFromInvitationCanAcceptInvitationSerializer(serializers.Serializer):
    _invitation_: Invitation
    _expanded_: list[ExpandedSessionFollowedInvitation]

    default_error_messages = {
        "invitation_not_found_in_session": _(
            "We couldn't find record of you following the invitation link for the "
            "invitation you're logging in for. Please follow the link again and "
            "try again. If there's still an issue, it could be that a previous browser "
            "session expired, or that something else went wrong. Also, browser cookies "
            "may be required for this portion of site functionality to work."
        )
    }

    invitation: serializers.PrimaryKeyRelatedField[Invitation] = (
        serializers.PrimaryKeyRelatedField(
            queryset=Invitation.objects.all().with_significant_relations_select_related()
        )
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        invitation: Invitation = validated_data["invitation"]
        self._invitation_ = invitation

        request: Request = self.context["request"]
        session = request._request.session
        expanded = get_invitations_followed_from_session(session)
        self._expanded_ = expanded

        expanded_found_for_this_invitation: list[ExpandedSessionFollowedInvitation] = []
        for record in expanded:
            if (
                record.pk == invitation.pk or str(record.pk) == str(invitation.pk)
            ) and (
                record.invitation.pk == invitation.pk
                or str(record.invitation.pk) == str(invitation.pk)
            ):
                expanded_found_for_this_invitation.append(record)
        if not expanded_found_for_this_invitation:
            self.fail("invitation_not_found_in_session")

        validated_data["can_accept_result"] = self.can_accept_result

        return validated_data

    @cached_property
    def can_accept_result(self) -> CanAcceptResult:
        try:
            invitation = self._invitation_
            expanded = self._expanded_
        except AttributeError as e:
            raise RuntimeError(
                "You must call `self.is_valid()` before trying to access "
                "`can_accept_result` on this serializer."
            ) from e
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )
        request: Request = self.context["request"]
        user: User = self.context["user"]
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return validate_can_accept_invitation(
            invitation,
            initiator=user,
            request=request._request,
            is_special_pre_user_creation_case=False,
            existing_invitations_followed_from_session=expanded,
        )


class LogoutSerializer(serializers.Serializer):
    pass


class CsrfSerializer(serializers.Serializer):
    pass


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=127)
    password_confirm = serializers.CharField(max_length=127)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        password = validated_data["password"]
        password_confirm = validated_data["password_confirm"]
        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        return validated_data


class SignupFromInvitationSerializer(SignupSerializer):
    invitation_id = serializers.IntegerField()


class SignupFromInvitationCanAcceptInvitationSerializer(serializers.Serializer):
    _invitation_: Invitation
    _signup_email_: str
    _expanded_: list[ExpandedSessionFollowedInvitation]

    default_error_messages = {
        "invitation_not_found_in_session": _(
            "We couldn't find record of you following the invitation link for the "
            "invitation you're signing up with. Please follow the link again and "
            "try again. If there's still an issue, it could be that a previous browser "
            "session expired, or that something else went wrong. Also, browser cookies "
            "may be required for this portion of site functionality to work."
        )
    }

    invitation: serializers.PrimaryKeyRelatedField[Invitation] = (
        serializers.PrimaryKeyRelatedField(
            queryset=Invitation.objects.all().with_significant_relations_select_related()
        )
    )
    signup_email = serializers.EmailField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        invitation: Invitation = validated_data["invitation"]
        self._invitation_ = invitation
        self._signup_email_ = validated_data["signup_email"]

        request: Request = self.context["request"]
        session = request._request.session
        expanded = get_invitations_followed_from_session(session)
        self._expanded_ = expanded

        expanded_found_for_this_invitation: list[ExpandedSessionFollowedInvitation] = []
        for record in expanded:
            if (
                record.pk == invitation.pk or str(record.pk) == str(invitation.pk)
            ) and (
                record.invitation.pk == invitation.pk
                or str(record.invitation.pk) == str(invitation.pk)
            ):
                expanded_found_for_this_invitation.append(record)
        if not expanded_found_for_this_invitation:
            self.fail("invitation_not_found_in_session")

        validated_data["can_accept_result"] = self.can_accept_result

        return validated_data

    @cached_property
    def can_accept_result(self) -> CanAcceptResult:
        try:
            invitation = self._invitation_
            signup_email = self._signup_email_
            expanded = self._expanded_
        except AttributeError as e:
            raise RuntimeError(
                "You must call `self.is_valid()` before trying to access "
                "`can_accept_result` on this serializer."
            ) from e
        assert invitation is not None and isinstance(invitation, Invitation), (
            "Pre-condition"
        )
        assert signup_email, "Pre-condition"
        request: Request = self.context["request"]

        temp_pre_signup_user: User = (
            construct_temporary_pre_persisted_user_for_acceptance_validation(
                email=signup_email
            )
        )

        return validate_can_accept_invitation(
            invitation,
            initiator=temp_pre_signup_user,
            request=request._request,
            is_special_pre_user_creation_case=True,
            existing_invitations_followed_from_session=expanded,
        )


class SignupResendVerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=False, allow_null=False)


class ResetPasswordBeginSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    secret_token = serializers.CharField()
    password = serializers.CharField()

    def validate_password(self, value: str) -> str:
        uidb64_user: User | None = self.context.get("uidb64_user")
        validate_password(value, uidb64_user)
        return value


class VerifyEmailSendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyEmailConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    secret_token = serializers.CharField()


class ChangeEmailRetrieveSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj: EmailChangeRequest) -> StrOrPromise:
        return obj.status.label

    class Meta:
        model = EmailChangeRequest
        fields = [
            "id",
            "user",
            "from_email",
            "to_email",
            "requested_at",
            "successfully_changed_at",
            "last_requested_a_new_from_or_to_email_at",
            "last_sent_a_change_email_at",
            "last_successfully_changed_at",
            "status",
            "status_label",
        ]
        read_only_fields = fields


class ChangeEmailRequestSerializer(serializers.Serializer):
    to_email = serializers.EmailField()


class ChangeEmailResendSerializer(serializers.Serializer):
    pass


class ChangeEmailConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    secret_token = serializers.CharField()
    password = serializers.CharField(max_length=255)


class ChangePasswordSerializer(serializers.Serializer):
    previous_password = serializers.CharField(max_length=127)
    new_password = serializers.CharField(max_length=127)
    new_password_confirm = serializers.CharField(max_length=127)

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"
        validate_password(value, user)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().validate(attrs)

        new_password = validated_data["new_password"]
        new_password_confirm = validated_data["new_password_confirm"]
        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )

        return validated_data
