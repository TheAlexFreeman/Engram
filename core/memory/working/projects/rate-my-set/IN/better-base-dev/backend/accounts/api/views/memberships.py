from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import NotRequired, TypedDict, cast

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

from backend.accounts.api.permissions.memberships import (
    MembershipBelongsToRequestingUser,
    MembershipOfRequestingUserIsOwner,
    MembershipSharesAccountWithRequestingUser,
)
from backend.accounts.ops.data_consistency import (
    check_account_memberships_consistency,
)
from backend.accounts.ops.users_app_states import (
    set_current_membership_in_all_places,
)
from backend.auth.api.permissions.verification import HasVerifiedEmail

from ...models.accounts import Account
from ...models.memberships import Membership, MembershipQuerySet
from ...models.users import User
from ...ops.memberships import delete_membership, update_membership_role
from ..serializers.memberships import (
    MembershipDestroySerializer,
    MembershipReadOnlyAccountNotIncludedSerializer,
    MembershipReadOnlySerializer,
    MembershipReadOnlyUserNotIncludedSerializer,
    MembershipSelectSerializer,
    MembershipUpdateRoleSerializer,
)


class MembershipViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    read_only_serializer_class: type[BaseSerializer] = MembershipReadOnlySerializer
    serializer_class = read_only_serializer_class
    queryset = (
        Membership.objects.all()
        .with_significant_relations_select_related()
        .with_role_priority()
        .with_default_role_priority_ordering()
    )
    permission_classes = [
        IsAuthenticated,
        HasVerifiedEmail,
        MembershipSharesAccountWithRequestingUser,
    ]

    def get_serializer_class(self):
        if self.action == "list":
            # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
            if getattr(self, "swagger_fake_view", False):  # pragma: no cover
                # ! NOTE: At the time of writing, Swagger won't necessarily be accurate
                # here with the `account` and/or `user` field unless the query params
                # are specified as intended for the request (with `account_id=` and/or
                # `user_id=` in the URL as desired/intended).
                if self.request.query_params.get("account_id"):
                    return MembershipReadOnlyAccountNotIncludedSerializer
                if self.request.query_params.get("user_id"):
                    return MembershipReadOnlyUserNotIncludedSerializer
                return self.read_only_serializer_class
            if (
                self.list_base_validated_query_params.account is None
                and self.list_base_validated_query_params.user is not None
            ):
                # At the time of writing, if we get into this `if` block, we *must* have
                # a `user` (and not an `account`) specified, so we are accessing or
                # querying memberships from a user's perspective. Hence, we'll assume we
                # should only include the account and not the user.
                return MembershipReadOnlyUserNotIncludedSerializer
            if self.list_base_validated_query_params.account is not None:
                # At the time of writing, if we get into this `if` block, we *must* have
                # a `account` specified, so we are accessing or querying memberships
                # from an account's perspective. Hence, we'll assume we should not
                # include the account but should include the user.
                return MembershipReadOnlyAccountNotIncludedSerializer
            return self.read_only_serializer_class
        if self.action == "retrieve":
            return self.read_only_serializer_class
        if self.action == "select":
            return MembershipSelectSerializer
        if self.action == "update_role":
            return MembershipUpdateRoleSerializer
        if self.action == "destroy":
            return MembershipDestroySerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = cast(MembershipQuerySet, super().get_queryset())

        # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
        if getattr(self, "swagger_fake_view", False):  # pragma: no cover
            return queryset

        # Maybe TODO: Move this into `django-filter` somehow as well?
        if self.action == "list" or not self.detail:
            validated_params = self.list_base_validated_query_params
            if validated_params.account is not None:
                queryset = queryset.filter(
                    account=validated_params.account
                ).with_default_role_priority_ordering()
            if validated_params.user is not None:
                queryset = queryset.filter(
                    user=validated_params.user
                ).with_user_last_selected_at_ordering()

        return queryset

    def get_permissions(self):
        permission_classes = [*self.permission_classes]

        if self.action == "destroy":
            permission_classes = [
                *permission_classes,
                (MembershipBelongsToRequestingUser | MembershipOfRequestingUserIsOwner),
            ]

        return [permission_class() for permission_class in permission_classes]

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

    @action(
        detail=True,
        methods=["post"],
        url_path="select",
        url_name="select",
        permission_classes=[
            *[p for p in permission_classes if p not in (HasVerifiedEmail,)],
            MembershipBelongsToRequestingUser,
        ],
    )
    def select(self, request: Request, *args, **kwargs) -> Response:
        user = request.user
        assert isinstance(user, User) and user.is_authenticated, "Pre-condition"
        membership: Membership = self.get_object()
        http_request = request._request
        write_serializer = self.get_serializer(instance=membership, data=request.data)
        write_serializer.is_valid(raise_exception=True)

        set_current_membership_in_all_places(
            user,
            membership,
            request=http_request,
            allow_unauthenticated_session=False,
        )

        return Response(data=write_serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="update-role",
        url_name="update-role",
        permission_classes=[*permission_classes, MembershipOfRequestingUserIsOwner],
    )
    def update_role(self, request, *args, **kwargs):
        membership: Membership = self.get_object()
        write_serializer = self.get_serializer(instance=membership, data=request.data)
        write_serializer.is_valid(raise_exception=True)
        validated_data = write_serializer.validated_data

        update_membership_role(
            membership,
            from_role=validated_data["from_role"],
            to_role=validated_data["to_role"],
        )

        return Response(data=write_serializer.data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance: Membership) -> None:
        serializer = self.get_serializer(instance=instance, data=self.request.data)
        serializer.is_valid(raise_exception=True)

        account = instance.account
        delete_membership(instance)
        check_account_memberships_consistency(account)

    @cached_property
    def user(self) -> User:
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"
        return user

    @cached_property
    def list_base_parsed_query_params_dict(self) -> ListBaseParsedQueryParamsDict:
        parsed: MembershipViewSet.ListBaseParsedQueryParamsDict = {}

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
