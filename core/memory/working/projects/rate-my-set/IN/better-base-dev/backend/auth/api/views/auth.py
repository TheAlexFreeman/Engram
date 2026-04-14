from __future__ import annotations

from contextlib import suppress
from typing import cast

from django.template import RequestContext
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_variables
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from backend.accounts.api.serializers.memberships import (
    MembershipReadOnlySerializer,
)
from backend.accounts.api.serializers.users import UserReadOnlySerializer
from backend.accounts.models.invitations import Invitation
from backend.accounts.models.users import User
from backend.accounts.ops.invitations import (
    CanAcceptResult,
    accept_invitation,
    restore_session_invitation_data,
)
from backend.accounts.ops.memberships import create_membership
from backend.accounts.ops.users_app_states import (
    set_current_membership_in_all_places,
)
from backend.accounts.types.users import UserCreatedFrom
from backend.auth.api.permissions.verification import HasVerifiedEmail
from backend.auth.api.serializers.auth import (
    ChangeEmailConfirmSerializer,
    ChangeEmailRequestSerializer,
    ChangeEmailResendSerializer,
    ChangeEmailRetrieveSerializer,
    ChangePasswordSerializer,
    CsrfSerializer,
    LoginFromInvitationCanAcceptInvitationSerializer,
    LoginFromInvitationSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshMeSerializer,
    ResetPasswordBeginSerializer,
    ResetPasswordConfirmSerializer,
    SignupFromInvitationCanAcceptInvitationSerializer,
    SignupFromInvitationSerializer,
    SignupResendVerificationEmailSerializer,
    SignupSerializer,
    VerifyEmailConfirmSerializer,
    VerifyEmailSendSerializer,
)
from backend.auth.models.email_changes import EmailChangeRequest
from backend.auth.ops.change_email import (
    FailedAttemptChangeEmailConfirmResult,
    FailedInitiateEmailChangeProcessResult,
    SuccessfulAttemptChangeEmailConfirmResult,
    SuccessfulInitiateEmailChangeProcessResultNotOnlyResend,
    SuccessfulInitiateEmailChangeProcessResultOnlyResend,
    attempt_change_email_confirm,
    initiate_email_change_process,
)
from backend.auth.ops.change_password import (
    FailedChangePasswordResult,
    SuccessfulChangePasswordResult,
    attempt_change_password,
)
from backend.auth.ops.login import (
    FailedLoginResult,
    SuccessfulLoginDidNotPerformLoginResult,
    SuccessfulLoginDidPerformLoginResult,
    attempt_login,
    perform_login,
)
from backend.auth.ops.logout import attempt_logout, perform_logout
from backend.auth.ops.reset_password import (
    FailedAttemptResetPasswordConfirmResult,
    FailedResetPasswordBeginResult,
    SuccessfulAttemptResetPasswordConfirmResult,
    SuccessfulResetPasswordBeginResult,
    attempt_reset_password_begin,
    attempt_reset_password_confirm,
    get_user_from_uidb64,
)
from backend.auth.ops.signup import (
    FailedSignupResendVerificationEmailResult,
    FailedSignupResult,
    SignupBlockedException,
    SuccessfulSignupResendVerificationEmailResult,
    SuccessfulSignupResult,
    attempt_signup,
    attempt_signup_resend_verification_email,
)
from backend.auth.ops.verify_email import (
    FailedAttemptVerifyEmailConfirmResult,
    FailedSendVerificationEmailResult,
    SuccessfulAttemptVerifyEmailConfirmResult,
    SuccessfulSendVerificationEmailResult,
    attempt_verify_email_confirm,
    send_verification_email,
)
from backend.base.ops.security import sensitive_drf_or_django_post_parameters
from backend.base.templatetags.initial_server_data_provided_for_web import (
    get_all_data,
    get_csrf_token,
)
from backend.utils.rest_framework.csrf import CsrfExemptSessionAuthentication
from backend.utils.transactions import is_in_transaction


class AuthViewSet(GenericViewSet):
    def get_serializer_class(self):
        if self.action == "refresh_me":
            return RefreshMeSerializer
        if self.action == "login":
            return LoginSerializer
        if self.action == "login_from_invitation":
            return LoginFromInvitationSerializer
        if self.action == "logout":
            return LogoutSerializer
        if self.action == "csrf":
            return CsrfSerializer
        if self.action == "signup":
            return SignupSerializer
        if self.action == "signup_from_invitation":
            return SignupFromInvitationSerializer
        if self.action == "signup_resend_verification_email":
            return SignupResendVerificationEmailSerializer
        if self.action == "reset_password_begin":
            return ResetPasswordBeginSerializer
        if self.action == "reset_password_confirm":
            return ResetPasswordConfirmSerializer
        if self.action == "verify_email_send":
            return VerifyEmailSendSerializer
        if self.action == "verify_email_confirm":
            return VerifyEmailConfirmSerializer
        if self.action == "change_email_retrieve":
            return ChangeEmailRetrieveSerializer
        if self.action == "change_email_request":
            return ChangeEmailRequestSerializer
        if self.action == "change_email_resend":
            return ChangeEmailResendSerializer
        if self.action == "change_email_confirm":
            return ChangeEmailConfirmSerializer
        if self.action == "change_password":
            return ChangePasswordSerializer
        return super().get_serializer_class()

    @action(
        detail=False,
        methods=["POST"],
        url_path="refresh-me",
        url_name="refresh_me",
        permission_classes=[permissions.AllowAny],
    )
    def refresh_me(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        # First, validate the provided refresh-me-related data (if there is any current
        # validation logic, etc.).
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="login",
        url_name="login",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(sensitive_drf_or_django_post_parameters("password"))
    @method_decorator(sensitive_variables("password", "validated_data"))
    def login(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        # First, validate the provided login-related data.
        serializer = self.get_serializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Next, attempt the login.
        result = attempt_login(
            request=request._request,
            email=validated_data["email"],
            password=validated_data["password"],
        )
        # If the login attempt fails, return the error response for that.
        if isinstance(result, FailedLoginResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        # Otherwise, if we get to here, we should have a
        # `SuccessfulLoginDidPerformLoginResult` and a `User` (`user`).
        assert isinstance(result, SuccessfulLoginDidPerformLoginResult), (
            "Post-condition"
        )
        user = result.user
        assert isinstance(user, User) and user.is_authenticated, "Post-condition"

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="login/from-invitation",
        url_name="login_from_invitation",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(sensitive_drf_or_django_post_parameters("password"))
    @method_decorator(sensitive_variables("password", "validated_data"))
    def login_from_invitation(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        # First, validate the provided login-related data.
        serializer = self.get_serializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Attempt the login, but don't actually perform the login (yet).
        login_result = attempt_login(
            request=request._request,
            email=validated_data["email"],
            password=validated_data["password"],
            just_validate=True,
        )
        # If the login attempt fails, return the error response for that.
        if isinstance(login_result, FailedLoginResult):
            return Response(
                data={
                    "non_field_errors": [login_result.message],
                    "_main_code_": login_result.code,
                },
                status=400,
            )
        # Otherwise, if we get to here, we should have a
        # `SuccessfulLoginDidPerformLoginResult` and a `User` (`user`).
        assert isinstance(login_result, SuccessfulLoginDidNotPerformLoginResult), (
            "Post-condition"
        )
        user = login_result.user
        assert isinstance(user, User) and user.is_authenticated, "Post-condition"

        next_serializer = LoginFromInvitationCanAcceptInvitationSerializer(
            data={"invitation": validated_data["invitation_id"]},
            context={**self.get_serializer_context(), "user": user},
        )
        next_serializer.is_valid(raise_exception=True)
        invitation: Invitation = next_serializer.validated_data["invitation"]
        can_accept_result: CanAcceptResult = next_serializer.validated_data[
            "can_accept_result"
        ]
        assert isinstance(invitation, Invitation), "Post-condition"
        assert isinstance(can_accept_result, CanAcceptResult), "Post-condition"

        # Accept the invitation.
        accept_invitation(invitation, user, can_accept_result=can_accept_result)

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

        # Now, perform the login.
        login_result.finalize_login()

        # Make the newly created `Membership` (`invitation_created_membership`) the
        # currently selected one.
        set_current_membership_in_all_places(
            user=user,
            membership=invitation_created_membership,
            request=request._request,
            allow_unauthenticated_session=False,
        )

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )
        all_data["new_membership"] = MembershipReadOnlySerializer(
            invitation_created_membership, context=self.get_serializer_context()
        ).data

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_name="logout",
        url_path="logout",
        permission_classes=[permissions.AllowAny],
    )
    def logout(self, request: Request) -> Response:
        attempt_logout(request=request._request)

        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="csrf",
        url_name="csrf",
        authentication_classes=[CsrfExemptSessionAuthentication],
        permission_classes=[permissions.AllowAny],
    )
    def csrf(self, request: Request) -> Response:
        context = RequestContext(request._request)
        csrf_token = get_csrf_token(context=context)
        return Response(data={"csrf_token": csrf_token}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="signup",
        url_name="signup",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "password", "password_confirm", "passwordConfirm"
        )
    )
    @method_decorator(
        sensitive_variables(
            "password", "password_confirm", "passwordConfirm", "validated_data"
        )
    )
    def signup(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        # NOTE: For now, if signup is attempted, we'll log the user out first. This
        # could be changed to simply throwing a validation error (400) if the user is
        # already logged in.
        if request.user.is_authenticated:
            perform_logout(request=request)

        # First, validate the provided signup-related data.
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        name = (
            " ".join(
                filter(
                    bool,
                    [
                        validated_data.get("first_name"),
                        validated_data.get("last_name"),
                    ],
                )
            )
            or ""
        )

        # Sign up - Create the `User` and anything else that happens under the hood,
        # etc.
        try:
            result = attempt_signup(
                email=validated_data["email"],
                name=name,
                password=validated_data["password"],
                create_user_from=UserCreatedFrom.DIRECT_SIGNUP,
            )
        except SignupBlockedException as e:
            return Response(
                data={
                    "non_field_errors": [e.message],
                    "_main_code_": e.code,
                },
                status=400,
            )
        # If the signup attempt fails, return the error response for that.
        if isinstance(result, FailedSignupResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulSignupResult), "Post-condition"
        # From here, we can populate the `user` from the `UserCreationResult` and
        # continue.
        user = result.user_creation_result.user

        # Log the user in.
        perform_login(request=request._request, user=user)

        # Send the verification email if the email is not verified at this point.
        if not user.email_is_verified:
            send_verification_email(email=user.email)

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )
        all_data["signup_user"] = UserReadOnlySerializer(
            user, context=self.get_serializer_context()
        ).data

        return Response(data=all_data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["POST"],
        url_path="signup/from-invitation",
        url_name="signup_from_invitation",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "password", "password_confirm", "passwordConfirm"
        )
    )
    @method_decorator(
        sensitive_variables(
            "password", "password_confirm", "passwordConfirm", "validated_data"
        )
    )
    def signup_from_invitation(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        # NOTE: For now, if signup from invitation is attempted, we'll log the user out
        # first. This could be changed to simply throwing a validation error (400) if
        # the user is already logged in.
        if request.user.is_authenticated:
            # By default, Django's logout calls `request.session.flush()`. That's fine,
            # except that we want to keep any invitation-related data in the session, so
            # we'll use `restore_session_invitation_data` to mark it before logging out
            # and then restore it after so that the invitation-related session data
            # persists past this logout here.
            with restore_session_invitation_data(request=request):
                perform_logout(request=request)

        # First, validate the provided signup-related data.
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        name = (
            " ".join(
                filter(
                    bool,
                    [
                        validated_data.get("first_name"),
                        validated_data.get("last_name"),
                    ],
                )
            )
            or ""
        )

        # Will be populated by `def pre_create_user_hook(...)` below (see `nonlocal
        # can_accept_result` and follows within there).
        can_accept_result: CanAcceptResult | None = None

        def pre_create_user_hook(*, email: str, **kwargs) -> None:
            nonlocal can_accept_result

            # Next, validate the invitation-related data, and that the provided
            # invitation can be accepted by the to-be-created user. If so, populate
            # `can_accept_result` with the successful result of the validation so that
            # it can be used later as required by `accept_invitation`.
            next_serializer = SignupFromInvitationCanAcceptInvitationSerializer(
                data={
                    "invitation": validated_data["invitation_id"],
                    "signup_email": email,
                },
                context=self.get_serializer_context(),
            )
            next_serializer.is_valid(raise_exception=True)
            invitation: Invitation = next_serializer.validated_data["invitation"]
            can_accept_result = next_serializer.validated_data["can_accept_result"]
            assert isinstance(invitation, Invitation), "Post-condition"
            assert (
                can_accept_result is not None
                and isinstance(can_accept_result, CanAcceptResult)
                and can_accept_result.can_attach_result.can_attach
                and can_accept_result.invitation == invitation
            ), "Post-condition"

        # Sign up - Create the `User` and anything else that happens under the hood,
        # etc.
        try:
            result = attempt_signup(
                email=validated_data["email"],
                name=name,
                password=validated_data["password"],
                create_user_from=UserCreatedFrom.ACCOUNT_INVITATION,
                # NOTE that `pre_create_user_hook` above will be called right before the
                # `User` gets created.
                pre_create_user_hooks=[pre_create_user_hook],
            )
        except SignupBlockedException as e:
            return Response(
                data={
                    "non_field_errors": [e.message],
                    "_main_code_": e.code,
                },
                status=400,
            )
        # If the signup (before `pre_create_user_hook` is called) part fails, return the
        # error response for that.
        if isinstance(result, FailedSignupResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        # Otherwise, if we get to here, we should have a `SuccessfulSignupResult` and a
        # `CanAcceptResult` with `can_attach_result.can_attach` True.
        assert isinstance(result, SuccessfulSignupResult), "Post-condition"
        # `pyright` does not understand that `can_accept_result` is/can be non-null here
        # (`mypy` does fine). This cast statement prevents the VS Code editor from
        # graying out everything underneath the assertion below.
        can_accept_result = cast(CanAcceptResult, can_accept_result)
        assert (
            can_accept_result is not None
            and isinstance(can_accept_result, CanAcceptResult)
            and can_accept_result.can_attach_result.can_attach
        ), "Post-condition"
        # From here, we can populate the `user` from the `UserCreationResult` and
        # continue.
        user = result.user_creation_result.user

        # Accept the invitation.
        accept_invitation(
            can_accept_result.invitation,
            user,
            can_accept_result=can_accept_result,
        )

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

        # Log the user in.
        perform_login(request=request._request, user=user)

        # Send the verification email if the email is not verified at this point.
        if not user.email_is_verified:
            send_verification_email(email=user.email)

        # Make the newly created `Membership` (`invitation_created_membership`) the
        # currently selected one.
        set_current_membership_in_all_places(
            user=user,
            membership=invitation_created_membership,
            request=request._request,
            allow_unauthenticated_session=False,
        )

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )
        all_data["new_membership"] = MembershipReadOnlySerializer(
            invitation_created_membership, context=self.get_serializer_context()
        ).data

        return Response(data=all_data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["POST"],
        url_path="signup/resend-verification-email",
        url_name="signup_resend_verification_email",
        permission_classes=[permissions.IsAuthenticated],
    )
    def signup_resend_verification_email(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        email = validated_data.get("email") or user.email

        result = attempt_signup_resend_verification_email(user=user, email=email)
        if isinstance(result, FailedSignupResendVerificationEmailResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulSignupResendVerificationEmailResult), (
            "Post-condition"
        )
        assert (
            result.user == user
            and result.user.is_authenticated
            and isinstance(result.user, User)
            and result.user.pk is not None
        ), "Post-condition"

        # Prepare the data for the frontend.
        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="reset-password/begin",
        url_name="reset_password_begin",
        permission_classes=[permissions.AllowAny],
    )
    def reset_password_begin(self, request: Request) -> Response:
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = attempt_reset_password_begin(email=validated_data["email"])
        if isinstance(result, FailedResetPasswordBeginResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulResetPasswordBeginResult), "Post-condition"

        return Response(data={}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="reset-password/confirm",
        url_name="reset_password_confirm",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "uidb_64", "uidb64", "secret_token", "secretToken", "password"
        )
    )
    @method_decorator(
        sensitive_variables(
            "uidb_64",
            "uidb64",
            "secret_token",
            "secretToken",
            "password",
            "validated_data",
        )
    )
    def reset_password_confirm(self, request: Request) -> Response:
        # Fix potential `djangorestframework_camel_case` undesired `underscoreize`
        # behavior here.
        data = dict(request.data)
        if "uidb_64" in data and "uidb64" not in data:
            data["uidb64"] = data.pop("uidb_64")

        uidb64_user: User | None = None
        uidb64 = data.get("uidb64")
        # Safety/sanity check.
        if uidb64 and isinstance(uidb64, str) and len(uidb64) <= 40_000:
            uidb64_user = get_user_from_uidb64(uidb64=uidb64)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=data,
            context={**self.get_serializer_context(), "uidb64_user": uidb64_user},
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = attempt_reset_password_confirm(
            request=request._request,
            uidb64=validated_data["uidb64"],
            secret_token=validated_data["secret_token"],
            only_check_uidb64_and_secret_token=False,
            password=validated_data["password"],
            login_if_successful=True,
            already_retrieved_uidb64_user=uidb64_user,
        )
        if isinstance(result, FailedAttemptResetPasswordConfirmResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulAttemptResetPasswordConfirmResult), (
            "Post-condition"
        )
        user = result.user
        assert isinstance(user, User) and user.is_authenticated, "Post-condition"

        # If the request is authenticated and the user's match (defensive programming),
        # update the request's user object to match the latest state of the user object
        # since these might not be the same object at the time of writing.
        if request.user.is_authenticated and request.user == user:
            request.user = user

        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="verify-email/send",
        url_name="verify_email_send",
        permission_classes=[permissions.AllowAny],
    )
    def verify_email_send(self, request: Request) -> Response:
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = send_verification_email(email=validated_data["email"])
        if isinstance(result, FailedSendVerificationEmailResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulSendVerificationEmailResult), (
            "Post-condition"
        )

        return Response(data={}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="verify-email/confirm",
        url_name="verify_email_confirm",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "uidb_64", "uidb64", "secret_token", "secretToken"
        )
    )
    @method_decorator(
        sensitive_variables(
            "uidb_64", "uidb64", "secret_token", "secretToken", "validated_data"
        )
    )
    def verify_email_confirm(self, request: Request) -> Response:
        # Fix potential `djangorestframework_camel_case` undesired `underscoreize`
        # behavior here.
        data = dict(request.data)
        if "uidb_64" in data and "uidb64" not in data:
            data["uidb64"] = data.pop("uidb_64")

        uidb64_user: User | None = None
        uidb64 = data.get("uidb64")
        # Safety/sanity check.
        if uidb64 and isinstance(uidb64, str) and len(uidb64) <= 40_000:
            uidb64_user = get_user_from_uidb64(uidb64=uidb64)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=data,
            context={**self.get_serializer_context(), "uidb64_user": uidb64_user},
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = attempt_verify_email_confirm(
            request=request._request,
            uidb64=validated_data["uidb64"],
            secret_token=validated_data["secret_token"],
            only_check_uidb64_and_secret_token=False,
            login_if_successful=False,
            already_retrieved_uidb64_user=uidb64_user,
        )
        if isinstance(result, FailedAttemptVerifyEmailConfirmResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulAttemptVerifyEmailConfirmResult), (
            "Post-condition"
        )
        user = result.user
        assert isinstance(user, User) and user.is_authenticated, "Post-condition"

        # If the request is authenticated and the user's match (defensive programming),
        # update the request's user object to match the latest state of the user object
        # since these wouldn't be the same object at the time of writing.
        if request.user.is_authenticated and request.user == user:
            request.user = user

        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["GET"],
        url_path="change-email/retrieve",
        url_name="change_email_retrieve",
        permission_classes=[permissions.IsAuthenticated, HasVerifiedEmail],
    )
    def change_email_retrieve(self, request: Request) -> Response:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        try:
            email_change_request: EmailChangeRequest = user.email_change_request
        except EmailChangeRequest.DoesNotExist:
            temporary_instance = EmailChangeRequest(id=-1, user=user)
            email_change_request = temporary_instance

        serializer = self.get_serializer(instance=email_change_request)

        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="change-email/request",
        url_name="change_email_request",
        permission_classes=[permissions.IsAuthenticated, HasVerifiedEmail],
    )
    def change_email_request(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_email = serializer.validated_data["to_email"]

        result = initiate_email_change_process(
            user=user,
            to_email=to_email,
            only_resend=False,
        )
        if isinstance(result, FailedInitiateEmailChangeProcessResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(
            result, SuccessfulInitiateEmailChangeProcessResultNotOnlyResend
        ), "Post-condition"

        response_data = ChangeEmailRetrieveSerializer(
            instance=result.email_change_request,
            context=self.get_serializer_context(),
        )

        return Response(data=response_data.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="change-email/resend",
        url_name="change_email_resend",
        permission_classes=[permissions.IsAuthenticated, HasVerifiedEmail],
    )
    def change_email_resend(self, request: Request) -> Response:
        assert is_in_transaction(), "Current pre-condition"

        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = initiate_email_change_process(
            user=user,
            to_email="use_email_change_request",
            only_resend=True,
        )
        if isinstance(result, FailedInitiateEmailChangeProcessResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(
            result, SuccessfulInitiateEmailChangeProcessResultOnlyResend
        ), "Post-condition"

        response_data = ChangeEmailRetrieveSerializer(
            instance=result.email_change_request,
            context=self.get_serializer_context(),
        )

        return Response(data=response_data.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="change-email/confirm",
        url_name="change_email_confirm",
        permission_classes=[permissions.AllowAny],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "uidb_64", "uidb64", "secret_token", "secretToken", "password"
        )
    )
    @method_decorator(
        sensitive_variables(
            "uidb_64",
            "uidb64",
            "secret_token",
            "secretToken",
            "password",
            "validated_data",
        )
    )
    def change_email_confirm(self, request: Request) -> Response:
        # Fix potential `djangorestframework_camel_case` undesired `underscoreize`
        # behavior here.
        data = dict(request.data)
        if "uidb_64" in data and "uidb64" not in data:
            data["uidb64"] = data.pop("uidb_64")

        uidb64_user: User | None = None
        uidb64 = data.get("uidb64")
        # Safety/sanity check.
        if uidb64 and isinstance(uidb64, str) and len(uidb64) <= 40_000:
            uidb64_user = get_user_from_uidb64(uidb64=uidb64)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=data,
            context={**self.get_serializer_context(), "uidb64_user": uidb64_user},
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = attempt_change_email_confirm(
            request=request._request,
            uidb64=validated_data["uidb64"],
            secret_token=validated_data["secret_token"],
            password=validated_data["password"],
            only_check_validation_conditions=False,
            check_password=True,
            login_if_successful=True,
            already_retrieved_uidb64_user=uidb64_user,
        )
        if isinstance(result, FailedAttemptChangeEmailConfirmResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulAttemptChangeEmailConfirmResult), (
            "Post-condition"
        )
        user = result.user
        assert isinstance(user, User) and user.is_authenticated, "Post-condition"

        # If the request is authenticated and the user's match (defensive programming),
        # update the request's user object to match the latest state of the user object
        # since these might not be the same object at the time of writing.
        if request.user.is_authenticated and request.user == user:
            request.user = user

        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )
        all_data["email_just_changed_to"] = result.to_email

        return Response(data=all_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["POST"],
        url_path="change-password",
        url_name="change_password",
        permission_classes=[permissions.IsAuthenticated, HasVerifiedEmail],
    )
    @method_decorator(
        sensitive_drf_or_django_post_parameters(
            "previous_password",
            "previousPassword",
            "new_password",
            "newPassword",
            "new_password_confirm",
            "newPasswordConfirm",
        )
    )
    @method_decorator(
        sensitive_variables(
            "previous_password",
            "previousPassword",
            "new_password",
            "newPassword",
            "new_password_confirm",
            "newPasswordConfirm",
            "validated_data",
        )
    )
    def change_password(self, request: Request) -> Response:
        assert is_in_transaction(), "Pre-condition"

        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        result = attempt_change_password(
            user,
            previous_password=validated_data["previous_password"],
            new_password=validated_data["new_password"],
            request=request._request,
        )
        if isinstance(result, FailedChangePasswordResult):
            return Response(
                data={
                    "non_field_errors": [result.message],
                    "_main_code_": result.code,
                },
                status=400,
            )
        assert isinstance(result, SuccessfulChangePasswordResult), "Post-condition"

        context = RequestContext(request._request)
        all_data = get_all_data(
            context=context,
            request=request._request,
            camel_case=False,
        )

        return Response(data=all_data, status=status.HTTP_200_OK)
