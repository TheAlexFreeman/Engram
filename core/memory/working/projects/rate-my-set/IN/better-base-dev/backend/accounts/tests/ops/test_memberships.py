from __future__ import annotations

from datetime import datetime

import pytest
from django.db import transaction
from pytest_subtests import SubTests

from backend.accounts.models.memberships import Membership
from backend.accounts.ops.data_consistency import (
    AccountDataConsistencyError,
    AccountsRelatedDataConsistencyErrorCode,
    check_account_memberships_consistency,
)
from backend.accounts.ops.memberships import (
    create_membership,
    delete_membership,
    update_membership_role,
    validate_can_create_membership,
    validate_can_delete_membership,
    validate_can_update_membership_role,
)
from backend.accounts.tests.factories import UserFactory
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.users import SKIP_MEMBERSHIP_CREATION
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.validation_errors import raises_validation_error


class TestCreateMembership:
    @pytest.mark.django_db
    def test_validate_can_create_membership(self, subtests: SubTests):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        m1 = u1._membership_factory_created_
        m2 = u2._membership_factory_created_

        with subtests.test(msg="Invalid: Not Owner"):
            with raises_validation_error(
                "You must be an account owner to create memberships."
            ):
                validate_can_create_membership(initiator=m2)

        with subtests.test(msg="Valid"):
            validate_can_create_membership(initiator=m1)

    @pytest.mark.django_db
    def test_create_membership(self, now: datetime):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership=SKIP_MEMBERSHIP_CREATION)
        assert not hasattr(u1, "membership"), "Pre-condition"

        m1 = create_membership(
            account=a1,
            user=u1,
            role=Role.OWNER,
        )

        assert m1.pk is not None
        assert m1.account == a1
        assert m1.user == u1
        assert m1.role == Role.OWNER
        assert m1.created >= now
        assert m1.modified >= m1.created


class TestUpdateMembershipRole:
    @pytest.mark.django_db
    def test_validate_can_update_membership_role(self, subtests: SubTests):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        u3 = UserFactory.create(membership__role=Role.OWNER)
        u4 = UserFactory.create(
            account=u3._account_factory_created_, membership__role=Role.OWNER
        )
        assert u1._account_ == u2._account_, "Pre-condition"
        assert u1._account_ != u3._account_, "Pre-condition"
        assert u3._account_ == u4._account_, "Pre-condition"
        m1 = u1._membership_factory_created_
        m2 = u2._membership_factory_created_
        m3 = u3._membership_factory_created_
        m4 = u4._membership_factory_created_

        for n, (m, i) in enumerate([(m1, m3), (m3, m1)]):
            with subtests.test(msg=f"Invalid: Accounts mismatch (case={n + 1})"):
                with raises_validation_error(
                    "You are not a member of the account associated with the membership "
                    "role you are trying to change."
                ):
                    validate_can_update_membership_role(
                        m,
                        initiator=i,
                        from_role=Role.OWNER,
                        to_role=Role.OWNER,
                    )

        for n, (m, i) in enumerate([(m1, m2), (m2, m2)]):
            with subtests.test(msg=f"Invalid: Not Owner (case={n + 1})"):
                with raises_validation_error(
                    "You must be an account owner to change membership roles."
                ):
                    validate_can_update_membership_role(
                        m,
                        initiator=i,
                        from_role=m.role,  # type: ignore[arg-type]
                        to_role=Role.MEMBER,
                    )

        with subtests.test(msg="Invalid: No owners remaining"):
            with raises_validation_error(
                "You cannot change the role of the only account owner to a "
                "non-owner role. Please add another owner before changing this "
                "role."
            ):
                validate_can_update_membership_role(
                    m1,
                    initiator=m1,
                    from_role=Role.OWNER,
                    to_role=Role.MEMBER,
                )

        for n, (m, i) in enumerate([(m2, m1), (m3, m4), (m4, m3)]):
            with subtests.test(msg=f"Valid (case={n + 1})"):
                validate_can_update_membership_role(
                    m,
                    initiator=i,
                    from_role=m.role,  # type: ignore[arg-type]
                    to_role=Role.MEMBER,
                )

    @pytest.mark.django_db
    def test_update_membership_role(self):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        m1 = u1._membership_factory_created_
        m2 = u2._membership_factory_created_
        assert m2.role == Role.MEMBER, "Pre-condition"

        update_membership_role(
            m2,
            from_role=Role.MEMBER,
            to_role=Role.OWNER,
            db_save_only_update_fields=True,
        )
        m2.refresh_from_db()

        assert m2.role == Role.OWNER
        assert m2.account == a1, "Sanity check"  # type: ignore[unused-ignore,unreachable]
        assert m2.user == u2, "Sanity check"

        update_membership_role(
            m2,
            from_role=Role.OWNER,
            to_role=Role.MEMBER,
            db_save_only_update_fields=False,
        )
        m2.refresh_from_db()

        assert m2.role == Role.MEMBER
        assert m2.account == a1, "Sanity check"
        assert m2.user == u2, "Sanity check"

        with pytest.raises(AccountDataConsistencyError) as exc_info3:
            update_membership_role(
                m1,
                from_role=Role.OWNER,
                to_role=Role.MEMBER,
                db_save_only_update_fields=False,
            )

        exception: AccountDataConsistencyError = exc_info3.value
        assert (
            exception.specific_error_code
            == AccountsRelatedDataConsistencyErrorCode.ACCOUNT_OWNERS_MISSING
        )
        assert (
            exception.specific_error_message == "The account does not have any owners."
        )


class TestDeleteMembership:
    @pytest.mark.django_db
    def test_validate_can_delete_membership(self, subtests: SubTests):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        u3 = UserFactory.create(membership__role=Role.OWNER)
        assert u1._account_ == u2._account_, "Pre-condition"
        assert u1._account_ != u3._account_, "Pre-condition"
        m1 = u1._membership_factory_created_
        m2 = u2._membership_factory_created_
        m3 = u3._membership_factory_created_

        for n, (m, i) in enumerate([(m1, m3), (m3, m1)]):
            with subtests.test(msg=f"Invalid: Accounts mismatch (case={n + 1})"):
                with raises_validation_error(
                    "You are not a member of the account associated with the membership "
                    "you are trying to delete."
                ):
                    validate_can_delete_membership(m, initiator=i)

        with subtests.test(msg=f"Invalid: Not Owner (case={n + 1})"):
            with raises_validation_error(
                "You must be an account owner to delete memberships."
            ):
                validate_can_delete_membership(m1, initiator=m2)

        with subtests.test(msg="Invalid: No members remaining"):
            with raises_validation_error(
                "You cannot delete a membership if it leaves the account with no "
                "members left. Please either add another member before deleting this "
                "membership or delete the account or final user instead."
            ):
                validate_can_delete_membership(m3, initiator=m3)

        with subtests.test(msg="Invalid: No owners remaining"):
            with raises_validation_error(
                "You cannot delete a membership if it leaves the account with no "
                "owners left. Please add another owner before deleting this membership "
                "or delete the remaining members."
            ):
                validate_can_delete_membership(m1, initiator=m1)

        for n, (m, i) in enumerate([(m2, m1), (m2, m2)]):
            with subtests.test(msg=f"Valid (case={n + 1})"):
                validate_can_delete_membership(m, initiator=i)

    @pytest.mark.django_db
    def test_delete_membership(self):
        a1 = AccountFactory.create()
        u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        m1 = u1._membership_factory_created_
        m2 = u2._membership_factory_created_
        assert m1.role == Role.OWNER, "Pre-condition"
        assert m2.role == Role.MEMBER, "Pre-condition"

        delete_membership(m2)
        with pytest.raises(Membership.DoesNotExist):
            m2.refresh_from_db()
        u2.delete()

        delete_membership(m1)
        with pytest.raises(Membership.DoesNotExist):
            m1.refresh_from_db()
        u1.delete()

        u3 = UserFactory.create(account=a1, membership__role=Role.OWNER)
        u4 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
        m3 = u3._membership_factory_created_
        m4 = u4._membership_factory_created_
        assert m3.role == Role.OWNER, "Pre-condition"
        assert m4.role == Role.MEMBER, "Pre-condition"

        m3_pk = m3.pk
        with (
            pytest.raises(AccountDataConsistencyError) as exc_info1,
            transaction.atomic(),
        ):
            delete_membership(m3)
            check_account_memberships_consistency(m3.account)
        m3.pk = m3_pk
        m3.refresh_from_db()

        e1: AccountDataConsistencyError = exc_info1.value
        assert (
            e1.specific_error_code
            == AccountsRelatedDataConsistencyErrorCode.ACCOUNT_OWNERS_MISSING
        )
        assert e1.specific_error_message == "The account does not have any owners."
        assert m3.role == Role.OWNER, "Post-condition"
