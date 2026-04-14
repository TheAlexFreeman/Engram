from __future__ import annotations

from typing import Final

from django.db import models
from django.db.models import Case, Q, When
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from backend.accounts.types.roles import Role, role_priority_mapping
from backend.base.models.core import CoreModel, CoreQuerySet

role_priority_hidden_attr: Final[str] = "_role_priority_"


class MembershipQuerySet(CoreQuerySet["Membership"]):
    def with_significant_relations_select_related(self):
        return self.select_related("account", "user")

    def with_role_priority(self):
        return self.annotate(
            role_priority=Case(  # type: ignore[no-redef]
                *[
                    When(role=role, then=priority)
                    for role, priority in role_priority_mapping.items()
                ],
                default=-1,
                output_field=models.IntegerField(),
            )
        )

    def with_default_role_priority_ordering(self):
        """
        NOTE: If using this, make sure to also use `with_role_priority` before this
        method.
        """
        return self.order_by(  # type: ignore[misc]
            "-role_priority",
            "created",
            "pk",
        )

    def with_user_last_selected_at_ordering(self):
        return self.order_by("-last_selected_at", "-user_id", "-pk")


class Membership(CoreModel):
    REPR_FIELDS = ("id", "account_id", "user_id", "role")

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        verbose_name=_("Account"),
        related_name="memberships",
        related_query_name="membership",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="memberships",
        related_query_name="membership",
    )

    role = models.CharField(
        "Role",
        choices=Role.choices,
        max_length=31,
    )

    last_selected_at = models.DateTimeField(
        _("Last Selected At"),
        default=timezone.now,
        help_text=_(
            "The last time the user created, switched to, or selected (etc.) this "
            "membership. This allows us to easily sort memberships by most recently "
            "selected."
        ),
    )

    objects = MembershipQuerySet.as_manager()

    def __str__(self) -> str:
        role_display: str = str(self.role)
        try:
            role_display = self.get_role_display()
        except Exception:
            pass
        return f"{self.user} - {role_display} of {self.account}"

    class Meta:
        constraints = [
            # Since `role` quite an important and sensitive field we do a more thorough
            # DB check constraint to really make sure it's always set to a valid role
            # value.
            models.CheckConstraint(
                condition=Q(role__in=[r.value for r in Role]),
                name="act_mbs_rl_cc",
            ),
            models.UniqueConstraint(
                fields=["account", "user"],
                name="act_mbs_ac_us_uix",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "last_selected_at"],
                name="act_mbs_us_ls_ix",
            )
        ]
        verbose_name = _("Membership")
        verbose_name_plural = _("Memberships")

    @property
    def role_priority(self) -> int:
        if hasattr(self, role_priority_hidden_attr):
            return getattr(self, role_priority_hidden_attr)
        return role_priority_mapping.get(self.role, -1)  # type: ignore[call-overload]

    @role_priority.setter
    def role_priority(self, value: int) -> None:
        setattr(self, role_priority_hidden_attr, value)
