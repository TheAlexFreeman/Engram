from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import admin
from django.http.request import HttpRequest
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from backend.accounts.models import Account
from backend.accounts.models.accounts import AccountQuerySet
from backend.accounts.types.roles import Role
from backend.base.admin.core import CoreModelAdmin

from .inlines.memberships import MembershipReadOnlyMax25ShownInlineModelAdmin


@admin.register(Account)
class AccountAdmin(CoreModelAdmin):
    list_display = [
        "id",
        "name",
        "account_type",
        "first_owner",
        "num_users",
        "num_owners",
        "num_members",
        "all_members",
        "created",
        "modified",
    ]
    list_filter = [
        "created",
        "modified",
    ]
    list_select_related = []
    search_fields = ["id", "name"]
    ordering = ["-pk"]

    fieldsets = (
        (
            None,
            {
                "fields": ("id",),
            },
        ),
        (
            _("Info"),
            {
                "fields": (
                    "name",
                    "account_type",
                    "uploaded_profile_image",
                )
            },
        ),
        (
            _("Members at a Glance"),
            {
                "fields": (
                    "first_owner",
                    "num_users",
                    "num_owners",
                    "num_members",
                    "all_members",
                )
            },
        ),
        (_("Metadata"), {"fields": ("created", "modified")}),
    )
    readonly_fields = [
        "id",
        "account_type",
        "created",
        "modified",
        "first_owner",
        "num_users",
        "num_owners",
        "num_members",
        "all_members",
    ]
    inlines = [MembershipReadOnlyMax25ShownInlineModelAdmin]

    can_add = False
    can_view = True
    can_change = True
    can_delete = False

    def get_queryset(self, request: HttpRequest):
        qs: AccountQuerySet = super().get_queryset(request)  # type: ignore[assignment]

        return (
            qs.with_initial_up_to_25_memberships_by_priority()
            .with_membership_counts_by_role()
            .with_total_memberships_counts()
        )

    @admin.display(description=_("First Owner"))
    def first_owner(self, obj: Account) -> str:
        if obj.first_owner is None:
            return ""
        # Link to the Django Admin `User` change page.
        url = reverse(
            "admin:accounts_user_change",
            args=(obj.first_owner.pk,),
        )
        return mark_safe(f'<a href="{url}">{obj.first_owner}</a>')

    @admin.display(description=_("# Users"))
    def num_users(self, obj: Account) -> int:
        if not obj.qs_pulled_in.has_total_memberships_count:
            raise ValueError(
                "This should have been pulled in with the queryset. Check "
                "`get_queryset` and/or wherever else."
            )
        return obj.qs_pulled_in.total_memberships_count

    @admin.display(description=_("# Owners"))
    def num_owners(self, obj: Account) -> int:
        if not obj.qs_pulled_in.has_membership_counts:
            raise ValueError(
                "This should have been pulled in with the queryset. Check "
                "`get_queryset` and/or wherever else."
            )
        return obj.qs_pulled_in.membership_counts[Role.OWNER]

    @admin.display(description=_("# Members"))
    def num_members(self, obj: Account) -> int:
        if not obj.qs_pulled_in.has_membership_counts:
            raise ValueError(
                "This should have been pulled in with the queryset. Check "
                "`get_queryset` and/or wherever else."
            )
        return obj.qs_pulled_in.membership_counts[Role.MEMBER]

    @admin.display(description=_("All Members"))
    def all_members(self, obj: Account) -> str:
        # Link to the Django Admin `Membership` changelist page with DjangoQL search
        # parameters set to filter to the current account.
        url = reverse("admin:accounts_membership_changelist")
        djangoql_search_params = {"q-l": "on", "q": f"account.id = {obj.pk}"}
        djangoql_search_encoded = urlencode(djangoql_search_params)
        return mark_safe(
            f'<a href="{url}?{djangoql_search_encoded}">View all members</a>'
        )
