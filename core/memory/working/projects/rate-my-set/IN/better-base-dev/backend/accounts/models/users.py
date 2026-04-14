from __future__ import annotations

import sys
from contextlib import suppress
from dataclasses import dataclass
from functools import cached_property
from secrets import token_urlsafe
from typing import Any, ClassVar, Self, TypeAlias

import structlog
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models import F, Q
from django.db.models.fields.files import FieldFile
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from model_utils.tracker import FieldTracker

from backend.accounts.models.accounts import Account
from backend.accounts.models.memberships import Membership, MembershipQuerySet
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom, UserCreationResult
from backend.base.models.core import CoreModel, CoreQuerySet
from backend.base.storages import get_default_public_media_storage
from backend.utils.case_insensitive_emails import (
    first_existing_with_email_case_insensitive,
)
from backend.utils.class_properties import cached_classproperty
from backend.utils.files import sanitize_filename_for_storage
from backend.utils.model_state import is_inserting
from backend.utils.transactions import is_in_transaction

logger = structlog.stdlib.get_logger()


@dataclass(frozen=True, slots=True, kw_only=True)
class AlreadyHashedPassword:
    hashed_password: str
    # Should not call `__init__` directly. Use `construct_from_non_hashed_password`.
    _do_not_set_outside_of_construct_from_non_hashed_password_: bool = True

    @sensitive_variables("self", "hashed_password", "self.hashed_password")
    def __post_init__(self):
        if (
            not self._do_not_set_outside_of_construct_from_non_hashed_password_
        ):  # pragma: no cover
            raise RuntimeError(
                "Attempted to use `AlreadyHashedPassword.__init__` for instantiation. "
                "Must use `construct_from_non_hashed_password`."
            )

    @classmethod
    @sensitive_variables("password", "hashed_password")
    def construct_from_non_hashed_password(cls, password: str | None) -> Self:
        hashed_password = make_password(password)
        return cls(
            hashed_password=hashed_password,
            _do_not_set_outside_of_construct_from_non_hashed_password_=True,
        )


PasswordType: TypeAlias = AlreadyHashedPassword | str | None


class UserQuerySet(CoreQuerySet["User"]):
    def first_existing_with_email_case_insensitive(self, email: str) -> User | None:
        return first_existing_with_email_case_insensitive(
            self.all(),
            email_field_name="email",
            email_value=email,
        )


class UserManagerBase(DjangoUserManager["User"]):
    # ! IMPORTANT: See NOTE in the docstring below. Do not call this directly in first
    # party code.
    @sensitive_variables("password")
    def create_user(  # type: ignore[override]
        self,
        *,
        email: str,
        password: PasswordType = None,
        account: Account | None = None,
        name: str | None = None,
        membership_role: Role | None = None,
        created_from: UserCreatedFrom = UserCreatedFrom.UNKNOWN,
        is_active: bool = True,
        is_staff: bool = False,
        is_superuser: bool = False,
        **extra_fields: Any,
    ) -> User:
        """
        * Important NOTE: This method *should not be used* in the code apart
        from internal Django auth or test code calling it. It's here so that we're
        compatible, out of the box, with Django's `createsuperuser` command and
        potentially other default test scaffolding related code (I.E. `pytest_django`'s
        `admin_user` and/or `admin_client` fixtures or others, etc.).

        What this method does is sets reasonable defaults for `create_user_op`
        (currently `backend.accounts.ops.users import create_user`) and then calls
        it. As mentioned above though, everywhere else in the first party code in the
        codebase *should be calling* `create_user_op` directly instead of this method.

        ^ The same applies to `create_superuser` below and `create_superuser_op`, etc.
        """
        extra_fields.pop("email", None)
        extra_fields.pop("password", None)

        use_membership_role: Role = (
            (Role.OWNER if account is None else Role.MEMBER)
            if membership_role is None
            else membership_role
        )

        creation_result: UserCreationResult = User.create_user_op(
            account=account,
            email=email,
            password=password,
            name=name,
            membership_role=use_membership_role,
            created_from=created_from,
            is_active=is_active,
            _is_staff_=is_staff,
            _is_superuser_=is_superuser,
            **extra_fields,
        )

        return creation_result.user

    # ! IMPORTANT: See NOTE in the docstring above for `create_user`. Do not call this
    # directly in first party code.
    @sensitive_variables("password")
    def create_superuser(  # type: ignore[override]
        self,
        *,
        email: str,
        password: PasswordType = None,
        account: Account | int | None = None,
        name: str | None = None,
        membership_role: Role = Role.OWNER,
        created_from: UserCreatedFrom = UserCreatedFrom.UNKNOWN,
        is_active: bool = True,
        is_staff: bool = True,
        is_superuser: bool = True,
        **extra_fields: Any,
    ) -> User:
        """
        * Important NOTE: See * Important NOTE above in `create_user`.
        """
        extra_fields.pop("email", None)
        extra_fields.pop("password", None)

        use_account: Account | None
        # NOTE: I put this in at the time of writing to get the standard builtin Django
        # `createsuperuser` management command to work properly, etc.
        if isinstance(account, int):
            use_account = Account.objects.get(pk=account)
        else:
            use_account = account

        use_created_from: UserCreatedFrom = created_from
        if created_from == UserCreatedFrom.UNKNOWN:
            try:
                if sys.argv and "createsuperuser" in sys.argv:
                    use_created_from = UserCreatedFrom.CREATE_SUPERUSER
            except Exception:
                pass

        creation_result: UserCreationResult = User.create_superuser_op(
            account=use_account,
            email=email,
            password=password,
            name=name,
            membership_role=membership_role,
            created_from=use_created_from,
            is_active=is_active,
            _is_staff_=is_staff,
            _is_superuser_=is_superuser,
            **extra_fields,
        )

        return creation_result.user

    # ! IMPORTANT: See NOTE in the docstring in the method below. Do not call this
    # directly in first party code apart from the one place it's already called.
    @sensitive_variables("password")
    def finalize_creating_user(
        self,
        *,
        email: str,
        password: PasswordType = None,
        **extra_fields: Any,
    ):
        """
        Important NOTE: This method *should not be used* in the code apart from being
        called by `User.create_user_op` (`backend.accounts.ops.users.create_user` at
        the time of writing).
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email, password, **extra_fields)

    # ! IMPORTANT: See NOTE in the docstring in the method below. Do not call this
    # directly in first party code apart from the one place it's already called.
    @sensitive_variables("password")
    def finalize_creating_superuser(
        self,
        *,
        email: str,
        password: PasswordType = None,
        **extra_fields: Any,
    ):
        """
        Important NOTE: This method *should not be used* in the code apart from being
        called by `User.create_user_op` (which is, right now at least, called by
        `User.create_superuser_op`, which is
        `backend.accounts.ops.users.create_user` at the time of writing).
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have `is_staff=True`.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have `is_superuser=True`.")

        return self._create_user(email, password, **extra_fields)

    @sensitive_variables("password", "hashed_password", "password.hashed_password")
    def _create_user(self, email: str, password: PasswordType, **extra_fields):
        """
        Create and save a `User` with the given `email` and `password`.
        """
        if not email:
            raise ValueError("The given `email` must be set.")

        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra_fields)
        if isinstance(password, AlreadyHashedPassword):
            user.password = password.hashed_password
        else:
            user.password = make_password(password)

        user.save(using=self._db)

        return user


# NOTE/TODO: If/once `django-stubs` supports generic `QuerySet`s attached to `Manager`s,
# we can update the type of `UserManagerBaseFromUserQuerySet` below.
UserManagerBaseFromUserQuerySet: type[UserManagerBase] = UserManagerBase.from_queryset(
    UserQuerySet
)


class UserManager(UserManagerBaseFromUserQuerySet):  # type: ignore[valid-type,misc]
    use_in_migrations = True


def user_profile_images_path(instance: User, filename: str):
    base = "uploads/images/users/profile_images"

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


class User(AbstractBaseUser, PermissionsMixin, CoreModel):
    REPR_FIELDS = ("id", "email", "name")

    email = models.EmailField(_("Email"), unique=True)
    email_is_verified = models.BooleanField(
        _("Email Is Verified?"),
        default=False,
        help_text=_("Has this User's email address been verified?"),
    )
    email_verified_as_of = models.DateTimeField(
        _("Email Verified As Of"),
        blank=True,
        null=True,
        help_text=_("When was this User's email address verified?"),
    )

    name = models.CharField(_("Name"), max_length=255, blank=True, default="")

    is_staff = models.BooleanField(
        _("Is Staff?"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("Is Active?"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Potentially unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("Date Joined"), default=timezone.now)

    created_from = models.CharField(
        _("Created From"),
        max_length=31,
        choices=UserCreatedFrom.choices,
        default=UserCreatedFrom.UNKNOWN,
        editable=False,
        help_text=_(
            "Where was this User created from? At this time of writing this might only "
            "be used for analytics purposes. Regardless though, it's a potentially "
            "useful field to have for customer support, debugging, or similar, etc. "
            "purposes if that ever arises, etc., and has plenty of other use cases as "
            "well."
        ),
    )

    uploaded_profile_image = models.ImageField(
        _("Uploaded Profile Image"),
        max_length=511,
        storage=get_default_public_media_storage,
        upload_to=user_profile_images_path,
        blank=True,
    )

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["name"]

    objects = UserManager()

    tracker = FieldTracker(fields=["uploaded_profile_image"])

    class Meta:
        constraints = [
            # The `email` cannot be blank.
            models.CheckConstraint(
                condition=~Q(email=""),
                name="act_usr_em_cc",
            ),
            # If `email_is_verified` is set to `True`, then `email_verified_as_of`
            # should not be `None`.
            models.CheckConstraint(
                condition=(
                    Q(email_is_verified=False) | Q(email_verified_as_of__isnull=False)
                ),
                name="act_usr_eiv_eva_cc",
            ),
            # NOTE: The `User`'s `email` must be unique in a case-insensitive manner.
            # While the RFC email spec is case-sensitive, most major email providers
            # (e.g. Gmail) do not treat email addresses as case-sensitive, and, I've
            # seen duplicate account issues, potential security issues, and other issues
            # arise from allowing multiple users to register with the same email address
            # but different casing. One example we saw on one project was that a user
            # might sometimes capitalize their email address when logging in, and
            # sometimes not, and this would cause duplicate accounts to be created.
            models.UniqueConstraint(
                Lower(F("email")),
                name="act_usr_em_fuix",
            ),
        ]
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self) -> str:
        return self.email

    @cached_classproperty
    def create_user_op(cls):
        from backend.accounts.ops.users import create_user

        return create_user

    @cached_classproperty
    def create_superuser_op(cls):
        from backend.accounts.ops.users import create_superuser

        return create_superuser

    @cached_property
    def active_memberships(self) -> MembershipQuerySet:
        return (
            self.memberships.all()
            .select_related("account")
            .with_role_priority()
            .with_user_last_selected_at_ordering()
        )

    @cached_property
    def account_id_to_membership_local_cache(self) -> dict[int, Membership]:
        """
        `get_membership_for_account_id` below can populate this. The usage of
        `@cached_property` allows for direct/straightforward deletion of the cache
        if/when needed.
        """
        return {}

    def clean(self) -> None:
        super().clean()

        self.email = self.__class__.objects.normalize_email(self.email)

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

        if is_inserting(self):
            # If `created` is specified, set `date_joined` to `created`.
            if self.created:
                self.date_joined = self.created
            # Otherwise, if `date_joined` is specified (and `created` is not), set
            # `created` to `date_joined`.
            elif self.date_joined:
                self.created = self.date_joined

            # If `created` is specified and `modified` is not specified, set it to
            # `created`.
            if self.created and not self.modified:
                self.modified = self.created

        save_result = super().save(*args, **kwargs)

        if needs_previous_image_deletion:
            self._try_and_delete_profile_image(
                override_what_to_delete=previous_uploaded_profile_image
            )

        return save_result

    def delete(self, *args, **kwargs):
        assert is_in_transaction(), "Pre-condition"

        initial_user_pk = self.pk
        has_uploaded_profile_image = bool(self.uploaded_profile_image)

        delete_result = super().delete(*args, **kwargs)

        if has_uploaded_profile_image:
            self._try_and_delete_profile_image(
                override_self_pk=initial_user_pk,
                did_just_delete_user=True,
            )

        return delete_result

    def get_full_name(self) -> str:
        return (self.name or "").strip()

    def get_short_name(self) -> str:
        name_stripped = (self.name or "").strip()
        name_split = name_stripped.split()
        return name_split[0] if name_split else ""

    def get_membership_for_account_id(
        self,
        account_id: int,
        *,
        nuke_cache: bool = False,
    ) -> Membership | None:
        """
        Get the `Membership` for the given `account_id` (`Account.pk`) for this `User`.
        Uses the `account_id_to_membership_local_cache` if the value if found in the
        cache.
        """
        if nuke_cache:
            with suppress(AttributeError):
                del self.account_id_to_membership_local_cache
            with suppress(AttributeError):
                del self.active_memberships

        has_active_memberships_been_pulled_in: bool = (
            "active_memberships" in self.__dict__
        )

        if account_id in self.account_id_to_membership_local_cache:
            return self.account_id_to_membership_local_cache[account_id]

        if (found := self._get_membership_for_account_id(account_id)) is not None:
            self.account_id_to_membership_local_cache[account_id] = found

        if found is None and not nuke_cache and has_active_memberships_been_pulled_in:
            return self.get_membership_for_account_id(account_id, nuke_cache=True)

        return found

    def get_account_for_account_id(self, account_id: int) -> Account | None:
        """
        Get the `Account` for the given `account_id` (`Account.pk`) for this `User`.
        Uses the `account_id_to_membership_local_cache` through
        `get_membership_for_account_id` if the value if found in the cache.
        """
        if (membership := self.get_membership_for_account_id(account_id)) is None:
            return None

        return membership.account

    def _get_membership_for_account_id(self, account_id: int) -> Membership | None:
        return next(
            (
                m
                for m in self.active_memberships
                if (
                    m.account_id is not None
                    and account_id is not None
                    and m.account_id == account_id
                )
            ),
            None,
        )

    def _try_and_delete_profile_image(
        self,
        *,
        override_what_to_delete: FieldFile | None = None,
        override_self_pk: int | None = None,
        did_just_delete_user: bool = False,
    ) -> bool:
        successfully_deleted: bool = False

        self_pk = self.pk if override_self_pk is None else override_self_pk
        self_email = self.email

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
                    "Ran into an error while trying to delete a `User`'s profile "
                    "image or previous profile image."
                ),
                user_pk=self_pk,
                user_email=self_email,
                uploaded_profile_image_name=profile_image.name,
                uploaded_profile_image_url=uploaded_profile_image_url,
                override_self_pk=override_self_pk,
                did_just_delete_user=did_just_delete_user,
            )
        else:
            successfully_deleted = True

        return successfully_deleted
