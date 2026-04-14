from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from functools import cached_property
from typing import NotRequired, TypedDict, cast

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet

from backend.accounts.api.permissions.invitations import (
    InvitationAccountHasRequestingUserAsOwner,
    InvitationEmailCaseInsensitiveEqualsUserEmail,
    InvitationSharesAccountWithRequestingUser,
)
from backend.accounts.api.serializers.memberships import (
    MembershipReadOnlySerializer,
)
from backend.accounts.ops.memberships import create_membership
from backend.accounts.ops.users_app_states import (
    set_current_membership_in_all_places,
)
from backend.auth.api.permissions.verification import HasVerifiedEmail
from backend.utils.transactions import is_in_transaction

from ...models.accounts import Account
from ...models.invitations import Invitation, InvitationQuerySet
from ...models.users import User
from ...ops.invitations import (
    accept_invitation,
    create_invitation,
    decline_invitation,
    delete_invitation,
    send_invitation,
    update_invitation,
)
from ..serializers.invitations import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationDeclineSerializer,
    InvitationDeleteSerializer,
    InvitationListAccountExcludedReadOnlySerializer,
    InvitationListReadOnlySerializer,
    InvitationListUserExcludedReadOnlySerializer,
    InvitationReadOnlySerializer,
    InvitationResendSerializer,
    InvitationUpdateSerializer,
)


class InvitationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    read_only_serializer_class: type[BaseSerializer] = InvitationReadOnlySerializer
    serializer_class = read_only_serializer_class
    queryset = (
        Invitation.objects.all()
        .with_significant_relations_select_related()
        .order_by("-pk")
    )
    permission_classes = [
        IsAuthenticated,
        HasVerifiedEmail,
        InvitationSharesAccountWithRequestingUser,
        InvitationAccountHasRequestingUserAsOwner,
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return InvitationCreateSerializer
        if self.action == "list":
            # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
            if getattr(self, "swagger_fake_view", False):  # pragma: no cover
                # ! NOTE: At the time of writing, Swagger won't necessarily be accurate
                # here with the `account` and/or `user` field unless the query params
                # are specified as intended for the request (with `account_id=` and/or
                # `user_id=` in the URL as desired/intended).
                if self.request.query_params.get("account_id"):
                    return InvitationListAccountExcludedReadOnlySerializer
                if self.request.query_params.get("user_id"):
                    return InvitationListUserExcludedReadOnlySerializer
                return InvitationListReadOnlySerializer
            if (
                self.list_base_validated_query_params.account is None
                and self.list_base_validated_query_params.user is not None
            ):
                # At the time of writing, if we get into this `if` block, we *must* have
                # a `user` through an `user_id` (and not an `account`) specified, so we
                # are accessing or querying memberships from a user's perspective.
                # Hence, we won't need to include the `user` field.
                return InvitationListUserExcludedReadOnlySerializer
            if self.list_base_validated_query_params.account is not None:
                # At the time of writing, if we get into this `if` block, we *must* have
                # a `account` specified, so we are accessing or querying memberships
                # from an account's perspective. Hence, we won't need to include the
                # `account` field.
                return InvitationListAccountExcludedReadOnlySerializer
            return InvitationListReadOnlySerializer
        if self.action == "retrieve":
            return InvitationReadOnlySerializer
        if self.action in ("update", "partial_update"):
            return InvitationUpdateSerializer
        if self.action == "resend":
            return InvitationResendSerializer
        if self.action == "accept":
            return InvitationAcceptSerializer
        if self.action == "decline":
            return InvitationDeclineSerializer
        if self.action == "destroy":
            return InvitationDeleteSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = cast(InvitationQuerySet, super().get_queryset())

        # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
        if getattr(self, "swagger_fake_view", False):  # pragma: no cover
            return queryset

        # --- QuerySet Filtering to Potentially Move Later ---
        # TODO: Move into `django-filter` once we're ready to do all of that. Probably
        # apply to/as the default queryset as well.
        now = timezone.now()
        raw_is_accepted_filter = self.request.query_params.get("is_accepted")
        raw_is_declined_filter = self.request.query_params.get("is_declined")
        raw_is_expired_filter = self.request.query_params.get("is_expired")
        _true_values = (True, "True", "true", "T", "t", 1, "1")
        _false_values = (False, "False", "false", "F", "f", 0, "0")
        if raw_is_accepted_filter in _true_values:
            queryset = queryset.filter(accepted_at__isnull=False)
        if raw_is_accepted_filter in _false_values:
            queryset = queryset.filter(accepted_at__isnull=True)
        if raw_is_declined_filter in _true_values:
            queryset = queryset.filter(declined_at__isnull=False)
        if raw_is_declined_filter in _false_values:
            queryset = queryset.filter(declined_at__isnull=True)
        if raw_is_expired_filter in _true_values:
            queryset = queryset.filter(expires_at__lt=now)
        if raw_is_expired_filter in _false_values:
            queryset = queryset.filter(expires_at__gte=now)
        # ---                                              ---

        # Maybe TODO: Move this into `django-filter` somehow as well?
        if (self.action == "list" or not self.detail) and self.action != "create":
            validated_params = self.list_base_validated_query_params
            if validated_params.account is not None:
                queryset = queryset.filter(account=validated_params.account)
            if validated_params.user is not None:
                queryset = queryset.filter(user=validated_params.user)

        return queryset.with_significant_relations_select_related().all()

    class ListBaseParsedQueryParamsDict(TypedDict):
        """
        When this is returned, it means the query params have been parsed *but not
        validated* until you access the `ListBaseValidatedQueryParams` (through
        `list_base_validated_query_params`).
        """

        account_id: NotRequired[int | None]
        user_id: NotRequired[int | None]

    @dataclass(frozen=True, kw_only=True, slots=True)
    class ListBaseValidatedQueryParams:
        """
        When this is returned, it means the query params have been parsed into this
        `ListBaseValidatedQueryParams` object (through
        `list_base_parsed_query_params_dict`) *and validated*.
        """

        account: Account | None
        user: User | None

        def __post_init__(self):
            if self.account is None and self.user is None:
                raise ValueError(
                    "Current pre-condition: `account` and `user` cannot both be `None` "
                    "at the same time."
                )

    def perform_create(self, serializer: InvitationCreateSerializer) -> None:  # type: ignore[override]
        validated_data = serializer.validated_data
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        account: Account = validated_data["account"]
        invited_by: User = validated_data["invited_by"]
        membership = invited_by.get_membership_for_account_id(account.pk)
        assert membership is not None, "Pre-condition"
        assert invited_by == user, "Pre-condition"

        invitation = create_invitation(
            account=account,
            invited_by=invited_by,
            email=validated_data["email"],
            name=validated_data["name"],
            role=validated_data["role"],
            delivery_method=validated_data["delivery_method"],
        )
        send_invitation(invitation)

        serializer.instance = invitation

    def perform_update(self, serializer: InvitationUpdateSerializer) -> None:  # type: ignore[override]
        obj: Invitation = serializer.instance  # type: ignore[assignment]
        validated_data = serializer.validated_data
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        account: Account = obj.account
        membership = user.get_membership_for_account_id(account.pk)
        assert membership is not None, "Pre-condition"
        name = validated_data.get("name") or None
        role = validated_data.get("role") or None

        if name or role:
            update_invitation(obj, name=name, role=role)

    def perform_destroy(self, instance: Invitation) -> None:
        assert is_in_transaction(), "Pre-condition"

        serializer = self.get_serializer(instance, data=self.request.data)
        serializer.is_valid(raise_exception=True)

        delete_invitation(instance, request=self.request._request)

    @action(
        detail=True,
        methods=["post"],
        url_path="resend",
        url_name="resend",
    )
    def resend(self, request: Request, *args, **kwargs):
        obj: Invitation = self.cached_object
        serializer = self.get_serializer(instance=obj, data=request.data or {})
        serializer.is_valid(raise_exception=True)

        send_invitation(obj)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="accept",
        url_name="accept",
        permission_classes=[
            IsAuthenticated,
            HasVerifiedEmail,
            InvitationEmailCaseInsensitiveEqualsUserEmail,
        ],
    )
    def accept(self, request: Request, *args, **kwargs):
        assert is_in_transaction(), "Pre-condition"

        obj: Invitation = self.cached_object
        serializer = self.get_serializer(instance=obj, data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as e:
            try:
                if (
                    isinstance(e.detail, dict)
                    and (non_field_errors := e.detail.get("non_field_errors"))
                    and isinstance(non_field_errors, list | tuple)
                    and hasattr(non_field_errors[0], "code")
                    and (
                        non_field_errors[0].code
                        == "email_mismatch_or_invalid_invitation"
                    )
                ):
                    raise PermissionDenied(
                        (
                            "For security reasons, In order to accept this particular "
                            "invitation, you need to follow the link for it sent to your "
                            "email."
                        ),
                        code="invitation_link_follow_likely_required",
                    ) from e
            except TypeError, ValueError, KeyError, AttributeError:
                pass
            raise
        assert isinstance(serializer, InvitationAcceptSerializer), "Pre-condition"
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        can_accept_result = serializer.can_accept_result
        # Accept the invitation.
        accept_invitation(obj, user, can_accept_result=serializer.can_accept_result)
        # Create the `Membership` for the `User` for the `Account` that the `Invitation`
        # is for.
        with suppress(AttributeError):
            del user.account_id_to_membership_local_cache
        with suppress(AttributeError):
            del user.active_memberships
        invitation_created_membership = create_membership(
            account=can_accept_result.invitation.account,
            user=user,
            role=can_accept_result.invitation.role,  # type: ignore[arg-type]
        )
        # Make the newly created `Membership` (`invitation_created_membership`) the
        # currently selected one.
        set_current_membership_in_all_places(
            user=user,
            membership=invitation_created_membership,
            request=request._request,
            allow_unauthenticated_session=False,
        )

        # Provide the newly created `Membership` to the frontend in addition to the
        # standard deserialized `Invitation` data.
        response_data = serializer.data
        response_data["new_membership"] = MembershipReadOnlySerializer(
            instance=invitation_created_membership,
            context=self.get_serializer_context(),
        ).data

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="decline",
        url_name="decline",
        permission_classes=[
            IsAuthenticated,
            HasVerifiedEmail,
            InvitationEmailCaseInsensitiveEqualsUserEmail,
        ],
    )
    def decline(self, request: Request, *args, **kwargs):
        assert is_in_transaction(), "Pre-condition"

        obj: Invitation = self.cached_object
        serializer = self.get_serializer(instance=obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        assert isinstance(serializer, InvitationDeclineSerializer), "Pre-condition"

        can_decline_result = serializer.can_decline_result
        # Decline the invitation.
        decline_invitation(obj, can_decline_result=can_decline_result)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @cached_property
    def user(self) -> User:
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"
        return user

    @cached_property
    def cached_object(self) -> Invitation:
        return self.get_object()

    @cached_property
    def list_base_parsed_query_params_dict(self) -> ListBaseParsedQueryParamsDict:
        parsed: InvitationViewSet.ListBaseParsedQueryParamsDict = {}

        for attribute in ("account_id", "user_id"):
            if attribute not in self.request.query_params:
                continue

            raw_attr_value = self.request.query_params.get(attribute)
            try:
                # Sanitize against incorrect extra large inputs, etc.
                if len(raw_attr_value or "") > 1_000:
                    attr_value = None
                else:
                    attr_value = int(raw_attr_value)  # type: ignore[arg-type]
            except TypeError, ValueError, OverflowError:
                attr_value = None

            if attribute == "account_id":
                parsed["account_id"] = attr_value
            else:
                assert attribute == "user_id", "Current pre-condition"
                parsed["user_id"] = attr_value

        return parsed

    @cached_property
    def list_base_validated_query_params(self) -> ListBaseValidatedQueryParams:
        requesting_user = self.user
        initially_parsed = self.list_base_parsed_query_params_dict
        account_id: int | None = initially_parsed.get("account_id")
        user_id: int | None = initially_parsed.get("user_id")

        if "account_id" in initially_parsed and initially_parsed["account_id"] is None:
            raise DRFValidationError(
                {
                    "non_field_errors": [
                        _("`account_id` must be a valid `Account` `id`."),
                    ]
                },
                code="invalid_query_param",
            )

        if "user_id" in initially_parsed and initially_parsed["user_id"] is None:
            raise DRFValidationError(
                {
                    "non_field_errors": [
                        _("`user_id` must be a valid `User` `id`."),
                    ]
                },
                code="invalid_query_param",
            )

        if account_id is None and user_id is None:
            raise DRFValidationError(
                {
                    "non_field_errors": [
                        _(
                            "You must provide at least one of `user_id` or `account_id` as a "
                            "query parameter.",
                        )
                    ]
                },
                code="missing_query_param",
            )

        account: Account | None = None
        if account_id is not None:
            if (
                account := requesting_user.get_account_for_account_id(account_id)
            ) is None:
                raise PermissionDenied(
                    _(
                        "You do not have a membership in the account you are "
                        "attempting to view or act on."
                    ),
                    code="missing_membership",
                )

        user_being_accessed: User | None = None
        if user_id is not None:
            if user_id == requesting_user.id:
                user_being_accessed = requesting_user
            elif account is None:
                raise PermissionDenied(
                    _(
                        "You cannot filter down to a specific user (`user_id`) without "
                        "that user being you or without filtering down to a specific "
                        "account (`account_id`) that you belong to as well."
                    ),
                    code="cannot_filter_down_to_user_without_account_unless_you",
                )
            else:
                user_being_accessed = User.objects.filter(id=user_id).first()

        return self.ListBaseValidatedQueryParams(
            account=account, user=user_being_accessed
        )
