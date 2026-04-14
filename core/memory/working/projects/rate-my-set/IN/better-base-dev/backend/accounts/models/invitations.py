from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from backend.accounts.types.invitations import DeliveryMethod, InvitationStatus
from backend.accounts.types.roles import Role
from backend.base.models.core import CoreModel, CoreQuerySet
from backend.utils.model_indexes import BrinOrFallbackIndex


class InvitationQuerySet(CoreQuerySet["Invitation"]):
    def with_significant_relations_select_related(self):
        return self.select_related("account", "invited_by", "user")


class Invitation(CoreModel):
    REPR_FIELDS = (
        "id",
        "account_id",
        "invited_by_id",
        "email",
        "name",
        "role",
        "user_id",
        "accepted_at",
        "status",
    )

    # The default amount of time after the `Invitation` is created that it will expire.
    default_expires_after: ClassVar[timedelta] = timedelta(days=30)
    # How soon before `expires_at` will we prevent an invitee (potential `User` that
    # would accept) from following the `Invitation` (I.E. clicking on an email link that
    # redirects the individual to a final acceptance/confirmation page)?
    #
    # We have this window as a way to prevent a potentially frustrating UX where the
    # `User` clicks on the link, potentially fills out some final information, and then
    # submits a form, only to be told that the `Invitation` has expired.
    cannot_follow_within: ClassVar[timedelta] = timedelta(minutes=15)

    # `Account` which the `Invitation` is for.
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        verbose_name=_("Account"),
        related_name="invitations",
        related_query_name="invitation",
        db_index=False,
    )
    # The `User` that invited the `user` to the `Account`.
    invited_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        verbose_name=_("Invited By"),
        related_name="invitations_sent",
        related_query_name="invitation_sent",
        blank=True,
        null=True,
    )

    # Invited `User` details (as set before invitation accepted).
    email = models.EmailField(_("Email"))
    name = models.CharField(_("Name"), max_length=255, blank=True)

    # Invited to be created (if accepted) `Membership` details (as set before invitation
    # accepted).
    role = models.CharField("Role", choices=Role.choices, max_length=31)

    # `User` that was invited and/or accepted invitation and datetime of acceptance
    # (if/once accepted) along with datetime of decline (if declined).
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="invitations",
        related_query_name="invitation",
        blank=True,
        null=True,
        default=None,
    )
    accepted_at = models.DateTimeField(
        _("Accepted At"),
        blank=True,
        null=True,
        default=None,
    )
    declined_at = models.DateTimeField(
        _("Declined At"),
        blank=True,
        null=True,
        default=None,
    )

    # Expiration
    expires_at = models.DateTimeField(_("Expires At"))

    # Security
    secret_token = models.CharField(
        _("Secret Token"),
        max_length=255,
        unique=True,
        editable=False,
    )

    # Delivery
    delivery_method = models.CharField(
        _("Delivery Method"),
        choices=DeliveryMethod.choices,
        max_length=31,
    )
    first_sent_at = models.DateTimeField(
        _("First Sent At"),
        blank=True,
        null=True,
        default=None,
    )
    last_sent_at = models.DateTimeField(
        _("Last Sent At"),
        blank=True,
        null=True,
        default=None,
    )
    num_times_sent = models.PositiveIntegerField(
        _("Number of Times Sent"),
        default=0,
    )
    delivery_data = models.JSONField(
        _("Delivery Data"),
        blank=True,
        null=True,
        default=None,
        encoder=DjangoJSONEncoder,
        help_text=_(
            "Data specific to the Delivery Method used and/or just general additional "
            "data on the delivery."
        ),
    )

    # Acceptance/Pre-Acceptance/Link Following/Etc. Analytics
    first_followed_at = models.DateTimeField(
        _("First Followed At"),
        blank=True,
        null=True,
        default=None,
    )
    last_followed_at = models.DateTimeField(
        _("Last Followed At"),
        blank=True,
        null=True,
        default=None,
    )
    num_times_followed = models.PositiveIntegerField(
        _("Number of Times Followed"),
        default=0,
    )

    objects = InvitationQuerySet.as_manager()

    class Meta:
        constraints = [
            # Should have at most one of `accepted_at` or `declined_at` set to `True`.
            models.CheckConstraint(
                condition=(
                    Q(accepted_at__isnull=True, declined_at__isnull=True)
                    | Q(accepted_at__isnull=True, declined_at__isnull=False)
                    | Q(accepted_at__isnull=False, declined_at__isnull=True)
                ),
                name="act_ivt_aa_da_cc",
            ),
            # Since `role` quite an important and sensitive field (on the `Membership`
            # which it will be set on) we do a more thorough DB check constraint to
            # really make sure it's always set to a valid role value. The same
            # constraint, at the time of writing, is also present on the `Membership`
            # model.
            models.CheckConstraint(
                condition=Q(role__in=sorted(r.value for r in Role)),
                name="act_ivt_rl_cc",
            ),
        ]
        indexes = [
            models.Index(
                fields=["account", "expires_at"],
                name="act_ivt_ac_ea_ix",
            ),
            models.Index(
                Lower(F("email")),
                "expires_at",
                condition=Q(
                    user_id__isnull=True,
                    accepted_at__isnull=True,
                    declined_at__isnull=True,
                ),
                name="act_ivt_em_ea_pix",
            ),
            BrinOrFallbackIndex(
                fields=["created"],
                name="act_ivt_cr_ix",
                autosummarize=True,
                pages_per_range=128,
            ),
        ]
        verbose_name = _("Invitation")
        verbose_name_plural = _("Invitations")

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    @property
    def is_declined(self) -> bool:
        return self.declined_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_past_follow_window(self) -> bool:
        return self.expires_at <= (timezone.now() + self.cannot_follow_within)

    @property
    def status(self) -> InvitationStatus:
        if self.is_accepted:
            return InvitationStatus.ACCEPTED
        if self.is_declined:
            return InvitationStatus.DECLINED
        if self.is_expired:
            return InvitationStatus.EXPIRED
        return InvitationStatus.OPEN

    @property
    def team_display_name(self) -> StrOrPromise:
        if self.account.name:
            return self.account.name
        elif (invited_by := self.invited_by) is not None and (name := invited_by.name):
            short_name = invited_by.get_short_name()
            return _("%(name)s's Team") % {"name": (short_name or name)}
        return _("a Team")

    @property
    def is_using_fallback_team_display_name(self) -> bool:
        return not self.account.name and (
            self.invited_by is None or not self.invited_by.name
        )

    @property
    def headline(self) -> StrOrPromise:
        """
        * Important NOTE: This can be, at the time of writing, used as an email
        subject line, so take that into consideration if/before changing it that you
        might want to change things there as well, etc.
        """
        return _("Join %(team_display_name)s on Better Base") % {
            "team_display_name": self.team_display_name
        }
