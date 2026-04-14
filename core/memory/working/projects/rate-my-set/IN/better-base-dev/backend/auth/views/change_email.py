from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_http_methods

from backend.auth.ops.change_email import (
    FailedAttemptChangeEmailConfirmResult,
    SuccessfulAttemptChangeEmailConfirmResult,
    attempt_change_email_confirm,
    change_email_redirect_run_preparation_logic,
)
from backend.base.ops.frontend_extra_signaling import (
    set_frontend_extra_data_to_bring_in,
    set_frontend_extra_signaling_data,
)


@never_cache
@require_http_methods(["GET"])
def change_email_redirect(
    request: HttpRequest, uidb64: str, secret_token: str
) -> HttpResponse:
    result = change_email_redirect_run_preparation_logic(
        request=request,
        uidb64=uidb64,
        secret_token=secret_token,
    )

    return redirect(
        "auth:change-email-confirm",
        uidb64=uidb64,
        secret_token=result.secret_token_to_use,
    )


@never_cache
@requires_csrf_token
@require_http_methods(["GET"])
def change_email_confirm(
    request: HttpRequest, uidb64: str, secret_token: str
) -> HttpResponse:
    initial_result = attempt_change_email_confirm(
        request=request,
        uidb64=uidb64,
        secret_token=secret_token,
        password="",
        only_check_validation_conditions=True,
        check_password=False,
        login_if_successful=False,
    )
    data: dict[str, Any] = {
        "uidb64": uidb64,
        "secret_token": secret_token,
        "is_valid": initial_result.uidb64_and_secret_token_valid,
    }
    if isinstance(initial_result, FailedAttemptChangeEmailConfirmResult):
        data["error_code"] = initial_result.code
        data["error_message"] = initial_result.message
    else:
        assert isinstance(initial_result, SuccessfulAttemptChangeEmailConfirmResult), (
            "Post-condition"
        )

    set_frontend_extra_signaling_data(
        request, immediately_redirect_to="changeEmailConfirm"
    )
    set_frontend_extra_data_to_bring_in(request, change_email_confirm=data)

    return render(request, "index.html")
