from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from backend.accounts.models import Account, Membership, User
from backend.accounts.ops.data_consistency import (
    check_account_and_membership_and_user_consistency_together,
)
from backend.accounts.types.roles import Role
from backend.utils.transactions import transaction_if_not_in_one_already


def validate_can_create_membership(
    *,
    initiator: Membership,
) -> None:
    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to create memberships."),
        )


def validate_can_update_membership_role(
    membership: Membership,
    *,
    initiator: Membership,
    from_role: Role,
    to_role: Role,
) -> None:
    # First, check the `initiator`.
    if initiator.account != membership.account:
        raise ValidationError(
            _(
                "You are not a member of the account associated with the membership "
                "role you are trying to change."
            ),
        )
    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to change membership roles."),
        )

    # Next, check `membership`, `from_role`, and `to_role`.
    account: Account = membership.account
    if from_role == Role.OWNER and to_role != Role.OWNER:
        has_other_owner: bool = (
            account.memberships.exclude(pk=membership.pk)
            .filter(role=Role.OWNER)
            .exists()
        )
        if not has_other_owner:
            raise ValidationError(
                _(
                    "You cannot change the role of the only account owner to a "
                    "non-owner role. Please add another owner before changing this "
                    "role."
                ),
            )


def validate_can_delete_membership(
    membership: Membership,
    *,
    initiator: Membership,
) -> None:
    # First, check the `initiator`.
    if initiator.account != membership.account:
        raise ValidationError(
            _(
                "You are not a member of the account associated with the membership "
                "you are trying to delete."
            ),
        )

    # If the `initiator` is the same as the `membership`, then we don't have to check
    # for ownership since members may manage themselves in this way (e.g., delete their
    # own membership).
    if initiator == membership:
        pass
    elif initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to delete memberships."),
        )

    # Next, check if the `account` would still be in a valid state.
    account: Account = membership.account
    remaining_roles: list[str] = list(
        account.memberships.exclude(pk=membership.pk)
        .values_list("role", flat=True)
        .distinct()
    )
    has_remaining_members = bool(remaining_roles)
    if not has_remaining_members:
        raise ValidationError(
            _(
                "You cannot delete a membership if it leaves the account with no "
                "members left. Please either add another member before deleting this "
                "membership or delete the account or final user instead."
            )
        )
    has_remaining_owner: bool = any(r for r in remaining_roles if r == Role.OWNER)
    if not has_remaining_owner:
        raise ValidationError(
            _(
                "You cannot delete a membership if it leaves the account with no "
                "owners left. Please add another owner before deleting this membership "
                "or delete the remaining members."
            ),
        )


def create_membership(
    *,
    account: Account,
    user: User,
    role: Role,
) -> Membership:
    with transaction_if_not_in_one_already():
        membership = Membership.objects.create(
            account=account,
            user=user,
            role=role,
        )

        check_account_and_membership_and_user_consistency_together(
            membership.account,
            membership,
            membership.user,
        )

    return membership


def update_membership_role(
    membership: Membership,
    *,
    from_role: Role,
    to_role: Role,
    db_save_only_update_fields: bool = True,
) -> None:
    assert membership.role == from_role, (
        "Pre-condition: This should not have been changed yet."
    )

    with transaction_if_not_in_one_already():
        membership.role = to_role

        if db_save_only_update_fields:
            membership.save(update_fields=["role", "modified"])
        else:
            membership.save()

        check_account_and_membership_and_user_consistency_together(
            membership.account,
            membership,
            membership.user,
        )


def delete_membership(membership: Membership) -> tuple[int, dict[str, int]]:
    with transaction_if_not_in_one_already():
        return membership.delete()
