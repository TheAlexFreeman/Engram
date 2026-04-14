from __future__ import annotations

from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from backend.base.models.core import CoreModel
from backend.utils.class_properties import cached_classproperty

if TYPE_CHECKING:
    from backend.auth.ops.change_email import EmailChangeRequestOps


class EmailChangeStatus(models.TextChoices):
    # No change has been requested yet, or the record has been reset to its empty state
    # (at the time of writing would have to query `EmailChangeRecord`s to know if it had
    # been changed before, etc.).
    EMPTY = "empty", _("Empty")

    # There is an open request to change the email that has not expired yet.
    PENDING = "pending", _("Pending")

    # There may be an open request to change the email but it has expired.
    EXPIRED = "expired", _("Expired")

    # The email has been successfully changed. At the time of writing, if we're in an
    # `EmailChangeRequest`, that means the `EmailChangeRequest` is holding the
    # successful results of the latest email change.
    SUCCESSFULLY_CHANGED = "successfully_changed", _("Successfully Changed")


class EmailChangeRequest(CoreModel):
    REPR_FIELDS = (
        "pk",
        "user_id",
        "to_email",
        "from_email",
        "status",
        "requested_at",
    )

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="email_change_request",
        verbose_name=_("User"),
    )

    # --- Current State ---
    from_email = models.EmailField(
        _("From Email"),
        blank=True,
        default="",
        help_text=_(
            "The email of the `User` at the time of the request (or blank if no "
            "request has been made yet)."
        ),
    )
    to_email = models.EmailField(
        _("To Email"),
        blank=True,
        default="",
        help_text=_(
            "The email that the `User` is requesting to change to (or blank if no "
            "request has been made yet)."
        ),
    )
    requested_at = models.DateTimeField(
        _("Requested At"),
        blank=True,
        null=True,
        default=None,
        help_text=_(
            "The timestamp of the latest time the user requested to change their "
            'email here from "From Email" to "To Email".'
        ),
    )
    successfully_changed_at = models.DateTimeField(
        _("Successfully Changed At"),
        blank=True,
        null=True,
        default=None,
        help_text=_(
            "The timestamp of when the email was successfully changed from "
            '"From Email" to "To Email" (if it was successfully changed).'
        ),
    )
    # ---               ---

    # --- Analytics ---
    last_requested_a_new_from_or_to_email_at = models.DateTimeField(
        _('Last Requested a New "From Email" or "To Email" At'),
        blank=True,
        null=True,
        default=None,
        editable=False,
        help_text=_(
            "The timestamp of the latest time the user requested a new email change "
            'to a different "To Email" and/or from a different "From Email".'
        ),
    )
    num_times_requested_a_new_from_or_to_email = models.PositiveIntegerField(
        _('Number of Times a New "From Email" or "To Email" Has Been Requested'),
        blank=True,
        default=0,
        editable=False,
        help_text=_(
            "The number of times the user requested a new email change to a different "
            '"To Email" and/or from a different "From Email".'
        ),
    )

    last_sent_a_change_email_at = models.DateTimeField(
        _("Last Sent a Change Email At"),
        blank=True,
        null=True,
        default=None,
        editable=False,
    )
    num_times_sent_a_change_email = models.PositiveIntegerField(
        _("Number of Times a Change Email Has Been Sent"),
        blank=True,
        default=0,
        editable=False,
    )

    last_successfully_changed_at = models.DateTimeField(
        _("Last Successfully Changed At"),
        blank=True,
        null=True,
        default=None,
        editable=False,
    )
    num_times_email_successfully_changed = models.PositiveIntegerField(
        _("Number of Times an Email Has Been Successfully Changed"),
        blank=True,
        default=0,
        editable=False,
    )
    # ---           ---

    class Meta:
        constraints = [
            models.CheckConstraint(
                # NOTE: At the time of writing, view code may use `-1` as an `id` to
                # construct a temporary record without actually creating it, etc. This
                # makes sure that value can't be persisted to the DB as the `id`.
                condition=~Q(id=-1),
                name="ath__ecr__id_not_-1_cc",
            ),
        ]
        verbose_name = _("Email Change Request")
        verbose_name_plural = _("Email Change Requests")

    def __str__(self):
        return (
            f"Email Change Request from {self.from_email} -> {self.to_email} for "
            f"<User: {self.user}>."
        )

    @cached_classproperty
    def ops_cls(cls) -> type[EmailChangeRequestOps]:
        from backend.auth.ops.change_email import EmailChangeRequestOps

        return EmailChangeRequestOps

    @cached_property
    def ops(self) -> EmailChangeRequestOps:
        return self.ops_cls(self)

    @property
    def status(self) -> EmailChangeStatus:
        if not self.from_email or not self.to_email or self.requested_at is None:
            return EmailChangeStatus.EMPTY
        if self.successfully_changed_at is not None:
            return EmailChangeStatus.SUCCESSFULLY_CHANGED
        now = timezone.now()
        timeout_seconds = settings.CHANGE_EMAIL_TIMEOUT
        timeout_timedelta = timedelta(seconds=timeout_seconds)
        if self.requested_at + timeout_timedelta >= now:
            return EmailChangeStatus.EXPIRED
        return EmailChangeStatus.PENDING


class SuccessfulEmailChange(CoreModel):
    REPR_FIELDS = (
        "pk",
        "user_id",
        "to_email",
        "from_email",
        "requested_at",
        "successfully_changed_at",
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="successful_email_changes",
        related_query_name="successful_email_change",
        verbose_name=_("User"),
    )

    from_email = models.EmailField(
        _("From Email"),
        help_text=_("The email of the `User` before the email change was made."),
    )
    to_email = models.EmailField(
        _("To Email"),
        help_text=_("The email of the `User` after the email change was made."),
    )
    requested_at = models.DateTimeField(
        _("Requested At"),
        help_text=_(
            "The timestamp of the latest request for the change before the successful "
            "email change was made."
        ),
    )
    successfully_changed_at = models.DateTimeField(
        _("Successfully Changed At"),
        help_text=_("The timestamp of when the email was successfully changed."),
    )

    class Meta:
        verbose_name = _("Successful Email Change")
        verbose_name_plural = _("Successful Email Changes")

    def __str__(self):
        return (
            f"Successful Email Change from {self.from_email} to {self.to_email} for "
            f"<User: {self.user}>."
        )
