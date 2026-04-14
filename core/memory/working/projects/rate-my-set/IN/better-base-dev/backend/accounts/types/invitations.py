from __future__ import annotations

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class DeliveryMethod(TextChoices):
    EMAIL = "email", _("Email")


class InvitationStatus(TextChoices):
    OPEN = "open", _("Open")
    ACCEPTED = "accepted", _("Accepted")
    DECLINED = "declined", _("Declined")
    EXPIRED = "expired", _("Expired")
