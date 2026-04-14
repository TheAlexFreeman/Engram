from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Final,
    Literal,
    NamedTuple,
    TypeAlias,
)

import structlog
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from django_stubs_ext import StrOrPromise

from backend.accounts.models import Account, Membership, User
from backend.accounts.models.users import PasswordType
from backend.accounts.ops.accounts import (
    create_personal_account,
    delete_account,
)
from backend.accounts.ops.data_consistency import (
    check_account_and_membership_and_user_consistency_together,
)
from backend.accounts.ops.memberships import delete_membership
from backend.accounts.ops.uploaded_images import (
    UserUpdateUploadedProfileImageFailedResult,
    UserUpdateUploadedProfileImageSuccessResult,
    update_uploaded_profile_image_op,
)
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom, UserCreationResult
from backend.utils.repr import NiceReprMixin
from backend.utils.transactions import (
    is_in_transaction,
)

logger = structlog.stdlib.get_logger()


@sensitive_variables("password")
def create_user(
    *,
    account: Account | None,
    email: str,
    password: PasswordType,
    name: str | None,
    membership_role: Role,
    created_from: UserCreatedFrom,
    is_active: bool = True,
    # Intentionally hide these so that they're not explicitly set to `True` without high
    # intent.
    _is_staff_: bool = False,
    _is_superuser_: bool = False,
    **extra_fields: Any,
) -> UserCreationResult:
    assert is_in_transaction(), "Pre-condition"

    extra_fields.setdefault("name", name or "")
    extra_fields.setdefault("created_from", created_from)
    extra_fields.setdefault("is_active", is_active)

    extra_fields.pop("is_staff", None)
    extra_fields.pop("is_superuser", None)
    extra_fields["is_staff"] = _is_staff_
    extra_fields["is_superuser"] = _is_superuser_

    with transaction.atomic():
        user: User
        if _is_superuser_:
            user = User.objects.finalize_creating_superuser(
                email=email,
                password=password,
                **extra_fields,
            )
        else:
            user = User.objects.finalize_creating_user(
                email=email,
                password=password,
                **extra_fields,
            )

        account_to_use: Account | None = account
        account_automatically_created: bool = False
        if account_to_use is None:
            account_to_use = create_personal_account(name="Personal Account")
            account_automatically_created = True
        assert account_to_use is not None, "Post-condition"
        assert account_automatically_created in (False, True), "Post-condition"

        membership = Membership.objects.create(
            account=account_to_use,
            user=user,
            role=membership_role,
        )

        check_account_and_membership_and_user_consistency_together(
            account_to_use,
            membership,
            user,
        )

    return UserCreationResult(
        user=user,
        account=account_to_use,
        account_automatically_created=account_automatically_created,
        membership=membership,
        is_active=is_active,
        is_staff=_is_staff_,
        is_superuser=_is_superuser_,
        created_from=created_from,
    )


@sensitive_variables("password")
def create_superuser(
    *,
    account: Account | None,
    email: str,
    password: PasswordType,
    name: str | None,
    membership_role: Role,
    created_from: UserCreatedFrom,
    is_active: bool = True,
    _is_staff_: bool = True,
    _is_superuser_: bool = True,
    **extra_fields: Any,
) -> UserCreationResult:
    assert is_in_transaction(), "Pre-condition"

    return create_user(
        account=account,
        email=email,
        password=password,
        name=name,
        membership_role=membership_role,
        created_from=created_from,
        is_active=is_active,
        _is_staff_=_is_staff_,
        _is_superuser_=_is_superuser_,
        **extra_fields,
    )


def update_user(user: User, *, name: str) -> None:
    assert is_in_transaction(), "Pre-condition"

    user.name = name
    user.save(update_fields=["name", "modified"])


def update_uploaded_profile_image(
    user: User, uploaded_profile_image: InMemoryUploadedFile
) -> (
    UserUpdateUploadedProfileImageSuccessResult
    | UserUpdateUploadedProfileImageFailedResult
):
    return update_uploaded_profile_image_op(user, uploaded_profile_image)  # type: ignore[return-value,unused-ignore]


@dataclass(frozen=True, kw_only=True, slots=True)
class DeleteUploadedProfileImageResult:
    user: User


def delete_uploaded_profile_image(user: User) -> DeleteUploadedProfileImageResult:
    assert is_in_transaction(), "Pre-condition"
    user.uploaded_profile_image.delete(save=False)
    user.save(update_fields=["uploaded_profile_image", "modified"])

    return DeleteUploadedProfileImageResult(user=user)


DELETE_ACCOUNT: Final[Literal["delete-account"]] = "delete-account"
DELETE_MEMBERSHIP: Final[Literal["delete-membership"]] = "delete-membership"
TRANSFER_OWNERSHIP: Final[Literal["transfer-ownership"]] = "transfer-ownership"
NOTIFY_OTHER_OWNERS: Final[Literal["notify-other-owners"]] = "notify-other-owners"

OTHER_OWNERS: Final[Literal["other-owners"]] = "other-owners"
OTHER_MEMBERS: Final[Literal["other-members"]] = "other-members"

# "delete-account" -> The entire `Account` will be deleted along with the current user's
# membership and any other memberships in the account.
#
# "delete-membership" -> The current user's membership will be deleted but the account
# will remain and the user will no longer have a membership in the account (in the small
# window before, presumably, the current user is deleted).
AutomatedPreDeleteActionType: TypeAlias = Literal[
    "delete-account",
    "delete-membership",
]

# "transfer-ownership" -> The user can or should transfer ownership of the account to a
# different membership in the account before continuing if required or desired, etc.
#
# "delete-account" -> The user can or should delete the account before continuing if
# required or desired, etc.
#
# "notify-other-owners" -> The user can or should notify the other owners in the account
# that it is leaving the account as an owner (because of the deletion that will happen)
# and that the other owners should take some action before continuing if required or
# desired, etc.
ManualPreDeleteActionType: TypeAlias = Literal[
    "transfer-ownership", "delete-account", "notify-other-owners"
]

# "other-owners" -> There are other owners in the account so the user will simply leave
# the account (by deleting the membership) rather than having the account deleted. If
# the user wants to delete the account then the user should do that first, or remove the
# other owners first (if that's allowed), or notify the other owners to take some
# action, etc.
#
# "other-members" -> There are other memberships in the account. If the user is the only
# owner then, by default, the account will be deleted. In that case, the user could
# choose to transfer ownership to a different membership in the account if desired.
ManualPreDeleteWarningType: TypeAlias = Literal["other-owners", "other-members"]


class AnnotatedAccountInfo(NamedTuple):
    account: Account
    is_owner: bool
    has_other_owner: bool
    has_other_member: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckUserDeletionAccountGroupings:
    # Accounts that the current user is the only owner of that do not have other
    # memberships in it.
    solo_owned_with_no_other_memberships: tuple[Account, ...]
    # Accounts that the current user is the only owner of that have other non-owner
    # memberships in it as well.
    solo_owned_with_other_memberships: tuple[Account, ...]
    # Accounts that the current user is an owner in and that also have other owners
    # besides the current user.
    jointly_owned: tuple[Account, ...]
    # Accounts that the current user is not an owner in.
    not_owner_in: tuple[Account, ...]
    # Important NOTE: At the time of writing, `other` should not have anything in it. If
    # it does, an error will be logged and either the `DELETE_ACCOUNT` or
    # `DELETE_MEMBERSHIP` action will be automatedly planned based on if there are other
    # memberships or not.
    other: tuple[tuple[Account, AnnotatedAccountInfo], ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckUserDeletionResult:
    user: User

    memberships: tuple[Membership, ...]

    can_delete_user: bool
    should_offer_manual_actions_before_deleting: bool

    account_groupings: CheckUserDeletionAccountGroupings
    automated_actions_planned: dict[Account, AutomatedPreDeleteActionType]
    manual_actions_required: dict[
        Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
    ]
    manual_actions_offered: dict[
        Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
    ]

    accounts_all_cleared: tuple[Account, ...]


class CheckUserDeletionOps(NiceReprMixin):
    REPR_FIELDS = ("user", "already_locked")

    class Plans(NamedTuple):
        automated_actions_planned: dict[Account, AutomatedPreDeleteActionType]
        manual_actions_required: dict[
            Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
        ]
        manual_actions_offered: dict[
            Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
        ]

        accounts_all_cleared: tuple[Account, ...]

    user: User
    memberships: QuerySet[Membership]
    already_locked: bool

    def __init__(self, user: User, *, already_locked: bool = False):
        assert is_in_transaction(), "Pre-condition"

        self.user = user

        self.already_locked = already_locked

    def check(self):
        assert is_in_transaction(), "Pre-condition"

        self._lock_and_set()

        assert self.user is not None and self.user.pk is not None, "Pre-condition"
        assert self.memberships is not None, "Post-condition"

        account_groupings = self._collect_accounts()
        plans = self._prepare_plans(account_groupings)

        can_delete_user: bool = not plans.manual_actions_required
        should_offer_manual_actions_before_deleting: bool = bool(
            plans.manual_actions_offered
        )

        return CheckUserDeletionResult(
            user=self.user,
            memberships=tuple(self.memberships),
            can_delete_user=can_delete_user,
            should_offer_manual_actions_before_deleting=should_offer_manual_actions_before_deleting,
            account_groupings=account_groupings,
            automated_actions_planned=plans.automated_actions_planned,
            manual_actions_required=plans.manual_actions_required,
            manual_actions_offered=plans.manual_actions_offered,
            accounts_all_cleared=plans.accounts_all_cleared,
        )

    def _lock_and_set(self) -> None:
        assert is_in_transaction(), "Pre-condition"

        self.memberships = (
            self.user.active_memberships.select_related("account", "user")
            .all()
            .with_user_last_selected_at_ordering()
        )

        if not self.already_locked:
            self.memberships = self.memberships.select_for_update()
            # Make sure to evaluate the `QuerySet` so that the locks are immediately
            # applied, etc.
            list(self.memberships)
            self.user.refresh_from_db()
        else:
            # Also make sure the `QuerySet` is evaluated in this branch/case for
            # consistent behavior with the other code branch.
            list(self.memberships)

    def _collect_accounts(self) -> CheckUserDeletionAccountGroupings:
        u = self.user
        memberships = self.memberships
        assert u is not None and u.pk is not None, "Pre-condition"
        assert memberships is not None, "Pre-condition"

        solo_owned_with_no_other_memberships: list[Account] = []
        solo_owned_with_other_memberships: list[Account] = []
        jointly_owned: list[Account] = []
        not_owner_in: list[Account] = []
        other: list[tuple[Account, AnnotatedAccountInfo]] = []

        annotated_info = self._collect_annotated_accounts_info()

        for m in memberships:
            account_info = annotated_info[m.account_id]
            if account_info.is_owner and (
                not account_info.has_other_owner and not account_info.has_other_member
            ):
                solo_owned_with_no_other_memberships.append(account_info.account)
            elif account_info.is_owner and not account_info.has_other_owner:
                solo_owned_with_other_memberships.append(account_info.account)
            elif account_info.is_owner and account_info.has_other_owner:
                jointly_owned.append(account_info.account)
            elif not account_info.is_owner:
                not_owner_in.append(account_info.account)
            else:  # pragma: no cover
                other.append((account_info.account, account_info))
                logger.error(
                    (
                        "Had to add to `CheckUserDeletionAccountGroupings.other` "
                        "which, at the time of writing, is not expected and may be the "
                        "result of incorrect code or data integrity somewhere else, "
                        "etc."
                    ),
                    stack_info=True,
                    user_id=u.pk,
                    account_id=account_info.account.pk,
                    membership_id=m.pk,
                    membership_account_id=m.account_id,
                    membership_user_id=m.user_id,
                )

        return CheckUserDeletionAccountGroupings(
            solo_owned_with_no_other_memberships=tuple(
                solo_owned_with_no_other_memberships
            ),
            solo_owned_with_other_memberships=tuple(solo_owned_with_other_memberships),
            jointly_owned=tuple(jointly_owned),
            not_owner_in=tuple(not_owner_in),
            other=tuple(other),
        )

    def _collect_annotated_accounts_info(self) -> dict[int, AnnotatedAccountInfo]:
        u = self.user
        memberships = self.memberships
        assert u is not None and u.pk is not None, "Pre-condition"
        assert memberships is not None, "Pre-condition"

        has_other_owner_attr = "_has_other_owner_"
        has_other_owner_subquery = Exists(
            Membership.objects.filter(account_id=OuterRef("id"))
            .exclude(user=u)
            .filter(role=Role.OWNER)
        )

        has_other_member_attr = "_has_other_member_"
        has_other_member_subquery = Exists(
            Membership.objects.filter(account_id=OuterRef("id"))
            .exclude(user=u)
            .exclude(role=Role.OWNER)
        )

        annotated_accounts: dict[int, AnnotatedAccountInfo] = {}
        for annotated_account in (
            Account.objects.all()
            .filter(id__in=memberships.values_list("account_id", flat=True))
            .annotate(
                **{
                    has_other_owner_attr: has_other_owner_subquery,
                    has_other_member_attr: has_other_member_subquery,
                }
            )
            .order_by("-id")
            .iterator(chunk_size=2_000)
        ):
            user_membership = next(
                m for m in memberships if m.account_id == annotated_account.id
            )
            is_owner = user_membership.role == Role.OWNER
            annotated_accounts[annotated_account.id] = AnnotatedAccountInfo(
                account=annotated_account,
                is_owner=is_owner,
                has_other_owner=getattr(annotated_account, has_other_owner_attr),
                has_other_member=getattr(annotated_account, has_other_member_attr),
            )

        return annotated_accounts

    def _prepare_plans(
        self, account_groupings: CheckUserDeletionAccountGroupings
    ) -> Plans:
        automated_actions_planned: dict[Account, AutomatedPreDeleteActionType] = {}
        manual_actions_required: dict[
            Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
        ] = {}
        manual_actions_offered: dict[
            Account, dict[ManualPreDeleteWarningType, list[ManualPreDeleteActionType]]
        ] = {}

        all_accounts: set[Account] = set()
        accounts_not_all_cleared: set[Account] = set()

        for account in account_groupings.solo_owned_with_no_other_memberships:
            automated_actions_planned[account] = DELETE_ACCOUNT
            all_accounts.add(account)

        for account in account_groupings.solo_owned_with_other_memberships:
            automated_actions_planned[account] = DELETE_ACCOUNT
            manual_actions_offered[account] = {OTHER_MEMBERS: [TRANSFER_OWNERSHIP]}
            all_accounts.add(account)
            accounts_not_all_cleared.add(account)

        for account in account_groupings.jointly_owned:
            automated_actions_planned[account] = DELETE_MEMBERSHIP
            manual_actions_offered[account] = {
                OTHER_OWNERS: [DELETE_ACCOUNT, NOTIFY_OTHER_OWNERS],
            }
            all_accounts.add(account)
            accounts_not_all_cleared.add(account)

        for account in account_groupings.not_owner_in:
            automated_actions_planned[account] = DELETE_MEMBERSHIP
            all_accounts.add(account)

        for (
            account,
            annotated_account_info,
        ) in account_groupings.other:  # pragma: no cover
            if annotated_account_info.has_other_owner:
                automated_actions_planned[account] = DELETE_MEMBERSHIP
                all_accounts.add(account)
            else:
                automated_actions_planned[account] = DELETE_ACCOUNT
                all_accounts.add(account)

        accounts_all_cleared = sorted(
            (all_accounts - accounts_not_all_cleared), key=lambda a: -1 * (a.pk)
        )

        return self.Plans(
            automated_actions_planned=automated_actions_planned,
            manual_actions_required=manual_actions_required,
            manual_actions_offered=manual_actions_offered,
            accounts_all_cleared=tuple(accounts_all_cleared),
        )


class CannotDeleteUserManualActionsRequiredError(RuntimeError):
    def __init__(
        self,
        message: StrOrPromise,
        code: str,
        check_result: CheckUserDeletionResult,
    ):
        super().__init__(message, code, check_result)

        self.message = message
        self.code = code
        self.check_result = check_result


@dataclass(frozen=True, kw_only=True, slots=True)
class DeleteUserResult:
    user: User
    check_result: CheckUserDeletionResult
    deletion_result: tuple[int, dict[str, int]]
    account_ids_deleted: tuple[int, ...]
    membership_ids_deleted: tuple[int, ...]
    user_id_deleted: int


def delete_user(user: User) -> DeleteUserResult:
    assert is_in_transaction(), "Pre-condition"
    assert user is not None and user.pk is not None, "Pre-condition"

    initial_user_id = user.pk

    check_instance = CheckUserDeletionOps(user, already_locked=False)
    check_result = check_instance.check()
    check_instance.already_locked = True

    if not check_result.can_delete_user:
        raise CannotDeleteUserManualActionsRequiredError(
            _(
                "This user cannot be deleted until the required manual actions are "
                "completed. Please reach out to support if this doesn't make sense or "
                "you need any assistance deleting this user."
            ),
            "requires_manual_actions",
            check_result,
        )

    memberships = check_instance.memberships
    account_ids_deleted: list[int] = []
    membership_ids_deleted: list[int] = []

    for account, action_type in check_result.automated_actions_planned.items():
        if action_type == DELETE_ACCOUNT:
            account_ids_deleted.append(account.id)
            delete_account(account)
        elif action_type == DELETE_MEMBERSHIP:
            membership_to_delete = next(
                m for m in memberships if m.account_id == account.id
            )
            membership_ids_deleted.append(membership_to_delete.id)
            delete_membership(membership_to_delete)
        else:
            raise RuntimeError(f'Unexpected/Unknown `action_type`: "{action_type}"')

    user_deletion_result = user.delete()

    return DeleteUserResult(
        user=user,
        check_result=check_result,
        deletion_result=user_deletion_result,
        account_ids_deleted=tuple(account_ids_deleted),
        membership_ids_deleted=tuple(membership_ids_deleted),
        user_id_deleted=initial_user_id,
    )
