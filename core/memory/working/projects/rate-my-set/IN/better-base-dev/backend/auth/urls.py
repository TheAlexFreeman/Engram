from __future__ import annotations

from django.urls import path

from .views.change_email import change_email_confirm, change_email_redirect
from .views.reset_password import reset_password_confirm, reset_password_redirect
from .views.verify_email import verify_email_confirm, verify_email_redirect

app_name = "auth"
urlpatterns = [
    path(
        "change-email/confirm/<uidb64>/<secret_token>",
        change_email_confirm,
        name="change-email-confirm",
    ),
    path(
        "change-email/redirect/<uidb64>/<secret_token>",
        change_email_redirect,
        name="change-email-redirect",
    ),
    path(
        "reset-password/confirm/<uidb64>/<secret_token>",
        reset_password_confirm,
        name="reset-password-confirm",
    ),
    path(
        "reset-password/redirect/<uidb64>/<secret_token>",
        reset_password_redirect,
        name="reset-password-redirect",
    ),
    path(
        "verify-email/confirm/<uidb64>/<secret_token>",
        verify_email_confirm,
        name="verify-email-confirm",
    ),
    path(
        "verify-email/redirect/<uidb64>/<secret_token>",
        verify_email_redirect,
        name="verify-email-redirect",
    ),
]
