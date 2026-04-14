from __future__ import annotations

from django.contrib import admin
from django.db.models import Case, Q, When
from django.db.models.functions import Now
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from backend.accounts.models import Invitation
from backend.accounts.types.invitations import InvitationStatus
from backend.base.admin.core import CoreModelAdmin


@admin.register(Invitation)
class InvitationAdmin(CoreModelAdmin):
    list_display = [
        "id",
        "account",
        "invited_by",
        "status",
        "email",
        "name",
        "role",
        "user",
        "accepted_at",
        "declined_at",
        "expires_at",
        "num_times_sent",
        "num_times_followed",
        "last_sent_at",
        "last_followed_at",
        "created",
        "modified",
    ]
    list_filter = [
        "role",
        "accepted_at",
        "declined_at",
        "expires_at",
        "last_sent_at",
        "last_followed_at",
        "created",
        "modified",
    ]
    list_select_related = ["account", "invited_by", "user"]
    search_fields = [
        "account__name",
        "invited_by__email",
        "invited_by__name",
        "email",
        "name",
        "user__email",
        "user__name",
    ]
    ordering = ["-pk"]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "id",
                ]
            },
        ),
        (
            "Inviter Details",
            {
                "fields": [
                    "account",
                    "invited_by",
                ]
            },
        ),
        (
            "Invitee Details",
            {
                "fields": [
                    "email",
                    "name",
                    "role",
                    "user",
                ]
            },
        ),
        (
            "Status Details",
            {
                "fields": [
                    "status_display",
                    "accepted_at",
                    "declined_at",
                    "expires_at",
                ]
            },
        ),
        (
            "Delivery and Followed Details",
            {
                "fields": [
                    "delivery_method",
                    "first_sent_at",
                    "last_sent_at",
                    "num_times_sent",
                    "pretty_delivery_data",
                    "first_followed_at",
                    "last_followed_at",
                    "num_times_followed",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "created",
                    "modified",
                ]
            },
        ),
    ]
    readonly_fields = [
        "id",
        "account",
        "invited_by",
        "email",
        "name",
        "role",
        "user",
        "accepted_at",
        "declined_at",
        "expires_at",
        "delivery_method",
        "first_sent_at",
        "last_sent_at",
        "num_times_sent",
        "delivery_data",
        "pretty_delivery_data",
        "first_followed_at",
        "last_followed_at",
        "num_times_followed",
        "created",
        "modified",
        "status_display",
    ]

    can_add = False
    can_view = True
    can_change = False
    can_delete = True

    @admin.display(description=_("Delivery Data"), ordering="delivery_data")
    def pretty_delivery_data(self, obj: Invitation) -> str:
        if obj.delivery_data is None:
            return ""
        return self.prettify_json_as_html(obj.delivery_data)

    @admin.display(
        description=_("Status"),
        ordering=Case(
            When(
                Q(accepted_at__isnull=False, user_id__isnull=False),
                then=InvitationStatus.ACCEPTED,
            ),
            When(declined_at__isnull=False, then=InvitationStatus.DECLINED),
            When(expires_at__lte=Now, then=InvitationStatus.EXPIRED),
            default=InvitationStatus.OPEN,
        ),
    )
    def status_display(self, obj: Invitation) -> StrOrPromise:
        assert isinstance(obj.status, InvitationStatus), "Current pre-condition"

        return obj.status.label
