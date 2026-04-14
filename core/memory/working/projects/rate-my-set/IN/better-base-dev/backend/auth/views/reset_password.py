from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_http_methods

from backend.auth.ops.reset_password import (
    FailedAttemptResetPasswordConfirmResult,
    SuccessfulAttemptResetPasswordConfirmResult,
    attempt_reset_password_confirm,
    reset_password_redirect_run_preparation_logic,
)
from backend.base.ops.frontend_extra_signaling import (
    set_frontend_extra_data_to_bring_in,
    set_frontend_extra_signaling_data,
)


@never_cache
@require_http_methods(["GET"])
def reset_password_redirect(
    request: HttpRequest, uidb64: str, secret_token: str
) -> HttpResponse:
    result = reset_password_redirect_run_preparation_logic(
        request=request,
        uidb64=uidb64,
        secret_token=secret_token,
    )

    return redirect(
        "auth:reset-password-confirm",
        uidb64=uidb64,
        secret_token=result.secret_token_to_use,
    )


@never_cache
@requires_csrf_token
@require_http_methods(["GET"])
def reset_password_confirm(
    request: HttpRequest, uidb64: str, secret_token: str
) -> HttpResponse:
    initial_result = attempt_reset_password_confirm(
        request=request,
        uidb64=uidb64,
        secret_token=secret_token,
        only_check_uidb64_and_secret_token=True,
        password="",
        login_if_successful=False,
    )
    data: dict[str, Any] = {
        "uidb64": uidb64,
        "secret_token": secret_token,
        "is_valid": initial_result.uidb64_and_secret_token_valid,
        "can_request_another_link": initial_result.could_request_another_link,
    }
    if isinstance(initial_result, FailedAttemptResetPasswordConfirmResult):
        data["error_code"] = initial_result.code
        data["error_message"] = initial_result.message
    else:
        assert isinstance(
            initial_result, SuccessfulAttemptResetPasswordConfirmResult
        ), "Post-condition"

    set_frontend_extra_data_to_bring_in(request, reset_password_confirm=data)
    set_frontend_extra_signaling_data(
        request, immediately_redirect_to="resetPasswordConfirm"
    )

    return render(request, "index.html")
