from __future__ import annotations

from dataclasses import dataclass

import structlog
from django.core.files.uploadedfile import InMemoryUploadedFile

from backend.accounts.models import Account
from backend.accounts.models.accounts import AccountType
from backend.accounts.ops.data_consistency import (
    check_account_memberships_consistency,
)
from backend.accounts.ops.uploaded_images import (
    AccountUpdateUploadedProfileImageFailedResult,
    AccountUpdateUploadedProfileImageSuccessResult,
    update_uploaded_profile_image_op,
)
from backend.utils.transactions import (
    is_in_transaction,
    transaction_if_not_in_one_already,
)

logger = structlog.stdlib.get_logger()


def create_account(
    *,
    account_type: AccountType,
    name: str,
) -> Account:
    name_to_use = name or f"{AccountType(account_type).label} Account"

    with transaction_if_not_in_one_already():
        return Account.objects.create(account_type=account_type, name=name_to_use)


def create_personal_account(*, name: str) -> Account:
    name_to_use = name or "Personal Account"

    return create_account(account_type=AccountType.PERSONAL, name=name_to_use)


def create_team_account(*, name: str) -> Account:
    name_to_use = name or "Team Account"

    return create_account(account_type=AccountType.TEAM, name=name_to_use)


def update_account(account: Account, *, name: str) -> None:
    with transaction_if_not_in_one_already():
        account.name = name or f"{AccountType(account.account_type).label} Account"

        account.save(update_fields=["name", "modified"])


def update_account_type(account: Account, *, new_account_type: AccountType) -> None:
    existing_account_type = account.account_type
    if (
        existing_account_type != AccountType.PERSONAL
        and new_account_type == AccountType.PERSONAL
    ):  # pragma: no cover
        raise NotImplementedError(
            "At the time of writing, we don't have an implementation for "
            "downgrading an account from a non-personal account to a personal account."
        )

    if existing_account_type == new_account_type:
        return

    with transaction_if_not_in_one_already():
        account.account_type = new_account_type

        account.save(update_fields=["account_type", "modified"])

        check_account_memberships_consistency(account)


def delete_account(account: Account) -> tuple[int, dict[str, int]]:
    with transaction_if_not_in_one_already():
        return account.delete()


def update_uploaded_profile_image(
    account: Account, uploaded_profile_image: InMemoryUploadedFile
) -> (
    AccountUpdateUploadedProfileImageSuccessResult
    | AccountUpdateUploadedProfileImageFailedResult
):
    response = update_uploaded_profile_image_op(account, uploaded_profile_image)
    return response


@dataclass(frozen=True, kw_only=True, slots=True)
class DeleteUploadedProfileImageResult:
    account: Account


def delete_uploaded_profile_image(account: Account) -> DeleteUploadedProfileImageResult:
    assert is_in_transaction(), "Pre-condition"

    account.uploaded_profile_image.delete(save=False)
    account.save(update_fields=["uploaded_profile_image", "modified"])

    return DeleteUploadedProfileImageResult(account=account)
