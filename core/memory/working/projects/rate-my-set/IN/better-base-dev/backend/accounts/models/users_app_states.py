from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.base.models.core import CoreModel


class UserAppState(CoreModel):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="app_state",
        unique=True,
    )

    current_membership_id = models.PositiveBigIntegerField(
        _("Current Membership Id"),
        blank=True,
        null=True,
        default=None,
    )
    current_membership_id_as_of = models.DateTimeField(
        _("Current Membership Id As Of"),
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = _("User App State")
        verbose_name_plural = _("Users App States")
