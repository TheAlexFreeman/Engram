from __future__ import annotations

from functools import cached_property

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import (
    BaseSerializer,
)
from rest_framework.serializers import (
    ValidationError as DRFValidationError,
)
from rest_framework.viewsets import GenericViewSet

from backend.accounts.api.permissions.users import UserIsRequestUser
from backend.accounts.api.serializers.users import (
    CheckUserDeletionSerializer,
    UserDeleteUploadedProfileImageSerializer,
    UserDestroySerializer,
    UserReadOnlySerializer,
    UserUpdateSerializer,
    UserUpdateUploadedProfileImageSerializer,
)
from backend.accounts.models.users import User
from backend.accounts.ops.uploaded_images import (
    UserUpdateUploadedProfileImageFailedResult,
    UserUpdateUploadedProfileImageSuccessResult,
)
from backend.accounts.ops.users import (
    CannotDeleteUserManualActionsRequiredError,
    CheckUserDeletionOps,
    delete_user,
    update_user,
)
from backend.accounts.ops.users import (
    delete_uploaded_profile_image as delete_uploaded_profile_image_op,
)
from backend.accounts.ops.users import (
    update_uploaded_profile_image as update_uploaded_profile_image_op,
)
from backend.auth.api.permissions.verification import HasVerifiedEmail
from backend.auth.ops.logout import perform_logout
from backend.utils.transactions import is_in_transaction


class UserViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    read_only_serializer_class: type[BaseSerializer] = UserReadOnlySerializer
    serializer_class = read_only_serializer_class
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, HasVerifiedEmail, UserIsRequestUser]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return self.read_only_serializer_class
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        if self.action == "destroy":
            return UserDestroySerializer
        if self.action == "update_uploaded_profile_image":
            return UserUpdateUploadedProfileImageSerializer
        if self.action == "delete_uploaded_profile_image":
            return UserDeleteUploadedProfileImageSerializer
        if self.action == "check_delete":
            return CheckUserDeletionSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()

        # https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
        if getattr(self, "swagger_fake_view", False):  # pragma: no cover
            return queryset

        # Restrict the queryset to the request's user.
        return queryset.filter(pk=self.requesting_user.pk)

    def perform_update(self, serializer: UserUpdateSerializer) -> None:  # type: ignore[override]
        user = serializer.instance
        assert user is not None and isinstance(user, User), "Pre-condition"
        if (name := serializer.validated_data.get("name")) is not None:
            update_user(user, name=name)

    def perform_destroy(self, instance: User) -> None:
        assert is_in_transaction(), "Pre-condition"

        serializer = self.get_serializer(instance=instance, data=self.request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delete_user(instance)
        except CannotDeleteUserManualActionsRequiredError as e:
            raise DRFValidationError({"non_field_errors": [e.message]}, e.code) from e

        if self.request.user == instance:
            perform_logout(request=self.request._request)

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

        user: User = self.get_object()
        serializer = self.get_serializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = update_uploaded_profile_image_op(
            user, validated_data["uploaded_profile_image"]
        )
        if isinstance(result, UserUpdateUploadedProfileImageFailedResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, UserUpdateUploadedProfileImageSuccessResult), (
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

        user: User = self.get_object()
        serializer = self.get_serializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        delete_uploaded_profile_image_op(user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        url_path="check-delete",
        url_name="check_delete",
        methods=["post"],
    )
    def check_delete(self, request: Request, *args, **kwargs) -> Response:
        assert is_in_transaction(), "Pre-condition"

        user: User = self.get_object()
        serializer = self.get_serializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)

        check_delete_ops = CheckUserDeletionOps(user, already_locked=False)
        result = check_delete_ops.check()

        serializer.instance = result

        return Response(serializer.data, status=status.HTTP_200_OK)

    @cached_property
    def requesting_user(self) -> User:
        user = self.request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"
        return user
