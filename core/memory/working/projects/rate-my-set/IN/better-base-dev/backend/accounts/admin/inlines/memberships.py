from __future__ import annotations

from django.contrib import admin
from django.http.request import HttpRequest
from django.utils.translation import gettext_lazy as _

from backend.accounts.models import Membership
from backend.accounts.models.memberships import MembershipQuerySet
from backend.base.admin.core import CoreInlineModelAdmin
from backend.utils.admin.formsets import BaseInlineFormSetWithLimit


class MembershipReadOnlyMax25ShownInlineFormSet(
    BaseInlineFormSetWithLimit, limit_number=25
):
    pass


class MembershipReadOnlyMax25ShownInlineModelAdmin(
    CoreInlineModelAdmin, admin.TabularInline
):
    formset = MembershipReadOnlyMax25ShownInlineFormSet
    model = Membership
    fields = [
        "id",
        "account",
        "user",
        "role",
        "user_name",
        "last_selected_at",
        "created",
        "modified",
    ]
    readonly_fields = [
        "id",
        "account",
        "user_name",
        "last_selected_at",
        "created",
        "modified",
    ]
    autocomplete_fields = ["user"]
    verbose_name_plural = _("Memberships (Up to 25 Max Shown)")
    extra = 0
    can_delete = True
    show_change_link = True

    can_add_inline = True
    can_change_inline = True
    can_delete_inline = True

    @admin.display(ordering="user__name", description=_("User's Name"))
    def user_name(self, obj: Membership) -> str:
        return obj.user.name or ""

    def get_queryset(self, request: HttpRequest):
        queryset: MembershipQuerySet = super().get_queryset(request)  # type: ignore[assignment]

        return (
            queryset.with_significant_relations_select_related()
            .with_role_priority()
            .with_default_role_priority_ordering()
        )
