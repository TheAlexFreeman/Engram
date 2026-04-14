from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from backend.accounts.models import Membership
from backend.base.admin.core import CoreModelAdmin


@admin.register(Membership)
class MembershipAdmin(CoreModelAdmin):
    list_display = [
        "id",
        "account",
        "user",
        "role",
        "last_selected_at",
        "created",
        "modified",
    ]
    list_filter = ["role", "last_selected_at", "created", "modified"]
    list_select_related = ["account", "user"]
    search_fields = ["account__name", "user__email", "user__name"]
    ordering = ["-pk"]

    fieldsets = (
        (None, {"fields": ("id", "account", "user")}),
        (_("Details"), {"fields": ("role",)}),
        (
            _("Metadata"),
            {"fields": ("created", "modified")},
        ),
    )
    readonly_fields = [
        "id",
        "account",
        "user",
        "role",
        "last_selected_at",
        "created",
        "modified",
    ]

    can_add = False
    can_view = True
    can_change = False
    can_delete = False
