from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.http.request import HttpRequest
from django.utils.translation import gettext_lazy as _

from backend.accounts.admin.forms.users import (
    UserAdminChangeForm,
    UserAdminCreationForm,
)
from backend.accounts.models import User
from backend.accounts.models.users import UserQuerySet
from backend.auth.ops.reset_password import attempt_reset_password_begin
from backend.auth.ops.verify_email import send_verification_email
from backend.base.admin.core import CoreModelAdmin


@admin.register(User)
class UserAdmin(CoreModelAdmin, auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            _("Personal info"),
            {
                "fields": (
                    "name",
                    "uploaded_profile_image",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Important dates"),
            {
                "fields": (
                    "last_login",
                    "date_joined",
                )
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "created_from",
                    "created",
                    "modified",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "account",
                    "email",
                    "name",
                    "membership_role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    list_display = [
        "email",
        "name",
        "email_is_verified",
        "created_from",
        "last_login",
        "email_verified_as_of",
        "date_joined",
        "is_superuser",
        "is_staff",
        "is_active",
        "modified",
    ]
    list_filter = [
        "email_is_verified",
        "created_from",
        "last_login",
        "email_verified_as_of",
        "date_joined",
        "is_superuser",
        "is_staff",
        "is_active",
        "modified",
    ]
    list_select_related = []
    search_fields = [
        "email",
        "name",
    ]
    ordering = ["-pk"]

    readonly_fields = [
        "created_from",
        "date_joined",
        "created",
        "modified",
    ]
    create_readonly_fields: list[str] = []
    update_readonly_fields: list[str] = []
    raw_id_fields: list[str] = []  # type: ignore[misc]

    actions = ["send_verification_or_password_reset_emails"]

    can_add = True
    can_view = True
    can_change = True
    can_delete = True

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None):
        if obj is None:
            return sorted(set(self.create_readonly_fields) | set(self.readonly_fields))
        return sorted(set(self.update_readonly_fields) | set(self.readonly_fields))

    def save_model(self, request: Any, obj: User, form: Any, change: Any) -> None:
        if change:
            return super().save_model(request, obj, form, change)
        # NOTE: The `UserAdminCreationForm` automatically creates and saves the `User`,
        # even if `commit=False`. This is tested in
        # `backend/accounts/tests/admin/test_users.py` at the time of writing.
        if obj.pk is None:
            raise RuntimeError(
                "Expecting the form to save the `User` instance no matter what."
            )

    @admin.action(description="Send Verification or Password Reset Emails")
    def send_verification_or_password_reset_emails(
        self, request: HttpRequest, queryset: UserQuerySet
    ) -> None:
        r_count: int = 0
        v_count: int = 0

        if queryset.count() > 7:
            self.message_user(
                request,
                (
                    "You can only send verification and/or password reset emails to 7 "
                    "or fewer users at a time."
                ),
                level=messages.ERROR,
            )
            return

        for user in queryset:
            if user.email_is_verified:
                attempt_reset_password_begin(email=user.email)
                r_count += 1
            else:
                send_verification_email(email=user.email)
                v_count += 1

        self.message_user(
            request,
            f"Sent {v_count} verification and {r_count} password reset email(s).",
            level=messages.SUCCESS,
        )
