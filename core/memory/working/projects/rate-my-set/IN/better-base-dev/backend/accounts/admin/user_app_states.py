from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from backend.accounts.models import UserAppState
from backend.base.admin.core import CoreModelAdmin


@admin.register(UserAppState)
class UserAppStateAdmin(CoreModelAdmin):
    list_display = [
        "user",
        "current_membership_id",
        "current_membership_id_as_of",
        "created",
        "modified",
    ]
    list_filter = ["current_membership_id_as_of", "created", "modified"]
    list_select_related = ["user"]
    search_fields = ["current_membership_id", "user__email", "user__name"]
    ordering = ["-pk"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "user",
                )
            },
        ),
        (
            _("Details"),
            {
                "fields": (
                    "current_membership_id",
                    "current_membership_id_as_of",
                ),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "created",
                    "modified",
                )
            },
        ),
    )
    readonly_fields = [
        "id",
        "user",
        "current_membership_id",
        "current_membership_id_as_of",
        "created",
        "modified",
    ]

    can_add = False
    can_view = False
    can_change = False
    can_delete = False
