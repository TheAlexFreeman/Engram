from __future__ import annotations

from enum import StrEnum
from typing import Final

from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from backend.accounts.models import Account, Membership, User
from backend.accounts.types.roles import Role
from backend.base.ops.exceptions import OpsError


class AccountsRelatedDataConsistencyErrorCode(StrEnum):
    # From `check_account_memberships_consistency`
    ACCOUNT_MEMBERS_MISSING = "account_members_missing"
    ACCOUNT_OWNERS_MISSING = "account_owners_missing"
    # From `check_membership_user_and_account_consistency`
    MEMBERSHIP_USER_MISSING = "membership_user_missing"
    MEMBERSHIP_ACCOUNT_MISSING = "membership_account_missing"
    USER_ACCOUNT_MISMATCH_WITH_MEMBERSHIP = "user_account_mismatch_with_membership"


accounts_related_data_consistency_error_code_to_default_error_message: Final[
    dict[AccountsRelatedDataConsistencyErrorCode, StrOrPromise]
] = {
    AccountsRelatedDataConsistencyErrorCode.ACCOUNT_MEMBERS_MISSING: _(
        "The account does not have any members."
    ),
    AccountsRelatedDataConsistencyErrorCode.ACCOUNT_OWNERS_MISSING: _(
        "The account does not have any owners."
    ),
    AccountsRelatedDataConsistencyErrorCode.MEMBERSHIP_USER_MISSING: _(
        "The membership is missing a user."
    ),
    AccountsRelatedDataConsistencyErrorCode.MEMBERSHIP_ACCOUNT_MISSING: _(
        "The membership is missing an account."
    ),
    AccountsRelatedDataConsistencyErrorCode.USER_ACCOUNT_MISMATCH_WITH_MEMBERSHIP: _(
        "The user's associated account for this membership is not the same as the "
        "membership's account."
    ),
}

assert list(map(str, [*AccountsRelatedDataConsistencyErrorCode])) == list(
    map(
        str,
        accounts_related_data_consistency_error_code_to_default_error_message.keys(),
    )
), "Current pre-condition"


class AccountsRelatedDataConsistencyError(OpsError):
    specific_error_code: AccountsRelatedDataConsistencyErrorCode
    specific_error_message: StrOrPromise

    def __init__(
        self,
        specific_error_code: AccountsRelatedDataConsistencyErrorCode,
        specific_error_message: StrOrPromise | None = None,
    ):
        self.specific_error_code = specific_error_code
        if not specific_error_message:
            self.specific_error_message = (
                accounts_related_data_consistency_error_code_to_default_error_message[
                    self.specific_error_code
                ]
            )
        else:
            self.specific_error_message = specific_error_message

        super().__init__(specific_error_code, specific_error_message)


class AccountDataConsistencyError(AccountsRelatedDataConsistencyError):
    """
    For consistency errors checked starting from the `Account` direction. Currently
    `def check_account_memberships_consistency(...)` below.
    """


class MembershipDataConsistencyError(AccountsRelatedDataConsistencyError):
    """
    For consistency errors checked starting from the `Membership` direction. Currently
    `def check_membership_user_and_account_consistency(...)` below.
    """


def raise_accounts_related_data_consistency_error(
    error_class: type[AccountsRelatedDataConsistencyError],
    error_key: AccountsRelatedDataConsistencyErrorCode,
    *,
    raise_from: Exception | None,
    override_error_message: str | None = None,
):
    if raise_from is None:
        raise error_class(error_key, override_error_message)
    else:
        raise error_class(error_key, override_error_message) from raise_from


def check_account_memberships_consistency(account: Account) -> None:
    """
    At the time of writing, check that:
    1. There is at least one `Membership` associated with the `account`.
    2. There is at least one `Membership` associated with the `account` that has
    `role == Role.OWNER`.
    """
    memberships: list[Membership] = list(account.memberships.all())
    if len(memberships) == 0:
        raise_accounts_related_data_consistency_error(
            AccountDataConsistencyError,
            AccountsRelatedDataConsistencyErrorCode.ACCOUNT_MEMBERS_MISSING,
            raise_from=None,
        )

    if not any(membership.role == Role.OWNER for membership in memberships):
        raise_accounts_related_data_consistency_error(
            AccountDataConsistencyError,
            AccountsRelatedDataConsistencyErrorCode.ACCOUNT_OWNERS_MISSING,
            raise_from=None,
        )


def check_membership_user_and_account_consistency(membership: Membership) -> None:
    """
    At the time of writing, check that:
    1. The `user` field on the `membership` is non-null and set to a `User`.
    2. The `account` field on the `membership` is non-null and set to an `Account`.
    3. The `account` associated with the user for the `membership` is the same as the
    `account` on the `membership` (`membership.account`).
    """
    user: User = membership.user
    if user is None:
        raise_accounts_related_data_consistency_error(  # type: ignore[unreachable]
            MembershipDataConsistencyError,
            AccountsRelatedDataConsistencyErrorCode.MEMBERSHIP_USER_MISSING,
            raise_from=None,
        )

    account: Account = membership.account
    if account is None:
        raise_accounts_related_data_consistency_error(  # type: ignore[unreachable]
            MembershipDataConsistencyError,
            AccountsRelatedDataConsistencyErrorCode.MEMBERSHIP_ACCOUNT_MISSING,
            raise_from=None,
        )

    account_from_user: Account | None = user.get_account_for_account_id(account.id)
    if account_from_user is None:
        raise_accounts_related_data_consistency_error(
            MembershipDataConsistencyError,
            AccountsRelatedDataConsistencyErrorCode.USER_ACCOUNT_MISMATCH_WITH_MEMBERSHIP,
            raise_from=None,
        )


def check_account_and_membership_and_user_consistency_together(
    account: Account, membership: Membership, user: User
) -> None:
    assert (
        account is not None and isinstance(account, Account) and account.pk is not None
    ), "Pre-condition"
    assert (
        membership is not None
        and isinstance(membership, Membership)
        and membership.pk is not None
    ), "Pre-condition"
    assert user is not None and isinstance(user, User) and user.pk is not None, (
        "Pre-condition"
    )

    check_account_memberships_consistency(account)
    check_membership_user_and_account_consistency(membership)
