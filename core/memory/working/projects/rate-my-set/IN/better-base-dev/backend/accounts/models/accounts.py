from __future__ import annotations

from functools import cached_property
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Final, Literal

import structlog
from django.db import models
from django.db.models import Count, Prefetch, Q
from django.db.models.fields.files import FieldFile
from django.utils.translation import gettext_lazy as _
from model_utils.tracker import FieldTracker

from backend.accounts.models.memberships import Membership
from backend.accounts.types.roles import Role, role_priority_mapping
from backend.base.models.core import CoreModel, CoreQuerySet
from backend.base.storages import get_default_public_media_storage
from backend.utils.files import sanitize_filename_for_storage
from backend.utils.transactions import is_in_transaction

logger = structlog.stdlib.get_logger()

if TYPE_CHECKING:
    from backend.accounts.models.users import User

all_memberships_prefetch_attr: Final[str] = "_all_memberships_"
initial_up_to_25_memberships_by_priority_prefetch_attr: Final[str] = (
    "_initial_up_to_25_memberships_by_priority_"
)
memberships_count_attr_format: Final[str] = "_memberships_count_{role}_"
total_memberships_count_attr: Final[str] = "_total_memberships_count_"


class AccountQuerySet(CoreQuerySet["Account"]):
    def with_all_memberships(self):
        prefetch = Prefetch(
            "memberships",
            queryset=(
                Membership.objects.all()
                .with_significant_relations_select_related()
                .with_role_priority()
                .with_default_role_priority_ordering()
            ),
            to_attr=all_memberships_prefetch_attr,
        )
        return self.prefetch_related(prefetch)

    def with_initial_up_to_25_memberships_by_priority(self):
        prefetch = Prefetch(
            "memberships",
            queryset=(
                Membership.objects.all()
                .with_significant_relations_select_related()
                .with_role_priority()
                .with_default_role_priority_ordering()[:25]
            ),
            to_attr=initial_up_to_25_memberships_by_priority_prefetch_attr,
        )
        return self.prefetch_related(prefetch)

    def with_membership_counts_by_role(self):
        return self.annotate(
            **{
                memberships_count_attr_format.format(role=role): Count(
                    "membership",
                    filter=Q(membership__role=role),
                    distinct=True,
                )
                for role in [*Role]
            },
        )

    def with_total_memberships_counts(self):
        return self.annotate(
            **{
                total_memberships_count_attr: Count(
                    "membership",
                    distinct=True,
                )
            },
        )


class AccountType(models.TextChoices):
    PERSONAL = "personal", _("Personal")
    TEAM = "team", _("Team")


def account_profile_images_path(instance: Account, filename: str):
    base = "uploads/images/accounts/profile_images"

    if filename and len(filename) <= 80:
        filename_to_use = filename or ""
    else:
        filename_to_use = "_" + (filename or "")[-79:]
    filename_to_use = sanitize_filename_for_storage(filename_to_use)

    if len(filename_to_use) < 10:
        filename_to_use = (
            token_urlsafe(8)[:8].replace("-", "_") + "--" + filename_to_use
        )

    filename_prefix = token_urlsafe(20)[:20].replace("-", "_")
    final_filename = sanitize_filename_for_storage(
        f"{filename_prefix}--{filename_to_use}"
    )

    return f"{base}/{final_filename}"


class Account(CoreModel):
    REPR_FIELDS = ("id", "account_type", "name")

    account_type = models.CharField(max_length=15, choices=AccountType)

    name = models.CharField(_("Name"), max_length=255, blank=True, default="")

    uploaded_profile_image = models.ImageField(
        _("Uploaded Profile Image"),
        max_length=511,
        storage=get_default_public_media_storage,
        upload_to=account_profile_images_path,
        blank=True,
    )

    objects = AccountQuerySet.as_manager()

    tracker = FieldTracker(fields=["uploaded_profile_image"])

    class Meta:
        constraints = [
            # Since `account_type` quite an important and sensitive field we do a more
            # thorough DB check constraint to really make sure it's always set to a
            # valid role value.
            models.CheckConstraint(
                condition=Q(account_type__in=[t.value for t in AccountType]),
                name="act_act_at_cc",
            )
        ]
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")

    def __str__(self):
        if self.name:
            return _("Account (pk=%(pk)s, account_type=%(account_type)s): %(name)s") % {
                "pk": self.pk,
                "account_type": self.account_type,
                "name": self.name,
            }
        if fallback_name := self.get_fallback_name(allow_db_query=False):
            return fallback_name
        return repr(self)

    def save(self, *args, **kwargs):
        previous_uploaded_profile_image = self.tracker.previous(
            "uploaded_profile_image"
        )
        next_uploaded_profile_image = self.uploaded_profile_image
        needs_previous_image_deletion = bool(
            previous_uploaded_profile_image
            and previous_uploaded_profile_image != next_uploaded_profile_image
        )

        if needs_previous_image_deletion:
            assert is_in_transaction(), "Pre-condition"

        save_result = super().save(*args, **kwargs)

        if needs_previous_image_deletion:
            self._try_and_delete_profile_image(
                override_what_to_delete=previous_uploaded_profile_image
            )

        return save_result

    def delete(self, *args, **kwargs):
        assert is_in_transaction(), "Pre-condition"

        initial_account_pk = self.pk
        has_uploaded_profile_image = bool(self.uploaded_profile_image)

        delete_result = super().delete(*args, **kwargs)

        if has_uploaded_profile_image:
            self._try_and_delete_profile_image(
                override_self_pk=initial_account_pk,
                did_just_delete_account=True,
            )

        return delete_result

    @cached_property
    def qs_pulled_in(self) -> AccountQuerySetPulledInData:
        return AccountQuerySetPulledInData(self)

    @cached_property
    def first_owner(self) -> User | None:
        pulled_in = self.qs_pulled_in
        first_owner: User | None = pulled_in.already_fetched_first_owner
        if first_owner is None:
            first_owner_membership = (
                Membership.objects.filter(account=self)
                .with_significant_relations_select_related()
                .with_role_priority()
                .with_default_role_priority_ordering()
                .first()
            )
            if first_owner_membership is not None:
                first_owner = first_owner_membership.user
        return first_owner

    def get_fallback_name(
        self,
        *,
        allow_db_query: bool = True,
        display_type: Literal["minimal", "detailed"] = "detailed",
    ) -> str:
        if display_type == "minimal":
            try:
                account_type_label = AccountType(self.account_type).label
            except TypeError, ValueError:
                account_type_label = (self.account_type or "").title()  # type: ignore[assignment]
            return _("%(account_type_label)s Account") % {
                "account_type_label": account_type_label
            }

        pulled_in = self.qs_pulled_in
        first_owner: User | None = pulled_in.already_fetched_first_owner
        if first_owner is None and allow_db_query:
            first_owner = self.first_owner

        if first_owner is not None:
            if first_owner.email and first_owner.name:
                return _(
                    "Account (pk=%(pk)s, account_type=%(account_type)s): "
                    "First Owner - %(email)s (%(name)s)"
                ) % {
                    "pk": self.pk,
                    "account_type": self.account_type,
                    "email": first_owner.email,
                    "name": first_owner.name,
                }
            elif first_owner.email:
                return _(
                    "Account (pk=%(pk)s, account_type=%(account_type)s): "
                    "First Owner - %(email)s"
                ) % {
                    "account_type": self.account_type,
                    "pk": self.pk,
                    "email": first_owner.email,
                }

        return _("Account (pk=%(pk)s, account_type=%(account_type)s): Unnamed") % {
            "pk": self.pk,
            "account_type": self.account_type,
        }

    def get_display_name(
        self,
        *,
        allow_db_query: bool = False,
        display_type: Literal["minimal", "detailed"] = "minimal",
    ) -> str:
        return self.name or self.get_fallback_name(
            allow_db_query=allow_db_query,
            display_type=display_type,
        )

    fallback_name = property(get_fallback_name)
    display_name = property(get_display_name)

    @property
    def membership_just_created(self) -> Membership:
        """
        If this `Account` was just created, this holds the `Membership` that was just
        created alongside it.
        """
        return self._membership_just_created

    @membership_just_created.setter
    def membership_just_created(self, value: Membership) -> None:
        self._membership_just_created = value

    def _try_and_delete_profile_image(
        self,
        *,
        override_what_to_delete: FieldFile | None = None,
        override_self_pk: int | None = None,
        did_just_delete_account: bool = False,
    ) -> bool:
        successfully_deleted: bool = False

        self_pk = self.pk if override_self_pk is None else override_self_pk
        self_name = self.name
        profile_image = (
            self.uploaded_profile_image
            if override_what_to_delete is None
            else override_what_to_delete
        )

        if not profile_image.name:
            return False

        try:
            # When `override_what_to_delete` comes from the `FieldTracker`, it is a
            # `LightStateFieldFile` whose `instance` is `None` (nullified to avoid
            # pickling the entire model). Calling `.delete()` on it crashes because
            # Django's `FieldFile.delete()` does `setattr(self.instance, ...)`. In
            # that case, delete the file from storage directly.
            profile_image_instance = getattr(profile_image, "instance", None)
            if profile_image_instance is None:
                profile_image.storage.delete(profile_image.name)
            else:
                profile_image.delete(save=False)
        except Exception:
            uploaded_profile_image_url = "<unknown>"

            try:
                uploaded_profile_image_url = profile_image.url
            except Exception:
                pass

            logger.exception(
                (
                    "Ran into an error while trying to delete a `Account`'s profile "
                    "image or previous profile image."
                ),
                account_pk=self_pk,
                account_name=self_name,
                uploaded_profile_image_name=profile_image.name,
                uploaded_profile_image_url=uploaded_profile_image_url,
                override_self_pk=override_self_pk,
                did_just_delete_account=did_just_delete_account,
            )
        else:
            successfully_deleted = True

        return successfully_deleted


class AccountQuerySetPulledInData:
    def __init__(self, account: Account):
        self.account = account

    @property
    def has_all_memberships(self) -> bool:
        return hasattr(self.account, all_memberships_prefetch_attr)

    @property
    def all_memberships(self) -> list[Membership]:
        return getattr(self.account, all_memberships_prefetch_attr)

    @property
    def has_initial_up_to_25_memberships_by_priority(self) -> bool:
        return hasattr(
            self.account, initial_up_to_25_memberships_by_priority_prefetch_attr
        )

    @property
    def initial_up_to_25_memberships_by_priority(self) -> list[Membership]:
        return getattr(
            self.account, initial_up_to_25_memberships_by_priority_prefetch_attr
        )

    @property
    def has_membership_counts(self) -> bool:
        first_role = list(role_priority_mapping.keys())[0]
        return hasattr(
            self.account, memberships_count_attr_format.format(role=first_role)
        )

    @property
    def membership_counts(self) -> dict[Role, int]:
        return {
            role: getattr(
                self.account,
                memberships_count_attr_format.format(role=role),
            )
            for role in [*Role]
        }

    @property
    def has_total_memberships_count(self) -> bool:
        return hasattr(self.account, total_memberships_count_attr)

    @property
    def total_memberships_count(self) -> int:
        return getattr(self.account, total_memberships_count_attr)

    @property
    def already_fetched_first_owner_membership(self) -> Membership | None:
        if (
            self.has_initial_up_to_25_memberships_by_priority
            and self.initial_up_to_25_memberships_by_priority
        ):
            return self.initial_up_to_25_memberships_by_priority[0]

        if self.has_all_memberships and self.all_memberships:

            def sorter(m: Membership):
                return (m.created, m.pk)

            return min(
                (m for m in self.all_memberships if m.role == Role.OWNER),
                key=sorter,
            )

        return None

    @property
    def already_fetched_first_owner(self) -> User | None:
        if (membership := self.already_fetched_first_owner_membership) is not None:
            return membership.user
        return None
