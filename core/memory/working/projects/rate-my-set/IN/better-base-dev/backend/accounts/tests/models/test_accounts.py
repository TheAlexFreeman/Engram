from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from backend.accounts.models import Account, Membership, User
from backend.accounts.models.accounts import AccountType
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.datetimes import Times


@dataclass
class CloneUserResult:
    account: Account
    membership: Membership
    user: User


@dataclass
class BulkCloneUsersResult:
    account: Account
    users: list[User]
    memberships: list[Membership]
    owners: list[Membership]
    members: list[Membership]
    num_owners: int
    num_members: int
    owner_indices: list[int]


@pytest.mark.django_db
class TestAccount:
    """
    Test the `Account` model, its properties/cached_properties, methods, etc., along
    with `AccountQuerySet` and `AccountQuerySetPulledInData`.
    """

    @pytest.fixture(autouse=True)
    def setup(self, times: Times, django_assert_num_queries) -> None:
        self.times = times
        self.now = self.times.now
        self.django_assert_num_queries = django_assert_num_queries

    @property
    def _next_now_incremented(self) -> datetime:
        return self.times.now_incremented

    def _clone_user(self, user: User, *, role: Role | None = None) -> CloneUserResult:
        counter_attr: str = "_clone_user_counter_"
        if not hasattr(self, counter_attr):
            setattr(self, counter_attr, 1)

        active_memberships = list(user.active_memberships)
        assert len(active_memberships) == 1, (
            "Current test potentially presumed pre-condition"
        )
        membership = user.active_memberships[0]

        new_email = f"cloned-{getattr(self, counter_attr)}-" + user.email
        new_role = role or membership.role

        next_timestamp = self._next_now_incremented

        cloned_user = deepcopy(user)
        cloned_user.pk = None
        cloned_user._state.adding = True
        cloned_user.email = new_email
        cloned_user.date_joined = next_timestamp
        cloned_user.created = next_timestamp
        cloned_user.modified = next_timestamp

        cloned_membership = deepcopy(membership)
        cloned_membership.pk = None
        cloned_membership._state.adding = True
        cloned_membership.user = cloned_user
        cloned_membership.role = new_role
        cloned_membership.created = next_timestamp
        cloned_membership.modified = next_timestamp

        setattr(self, counter_attr, getattr(self, counter_attr) + 1)

        return CloneUserResult(
            account=cloned_membership.account,
            membership=cloned_membership,
            user=cloned_user,
        )

    def _bulk_clone_users(self, user: User) -> BulkCloneUsersResult:
        active_memberships = list(user.active_memberships)
        assert len(active_memberships) == 1, (
            "Current test potentially presumed pre-condition"
        )
        account = user.active_memberships[0].account

        # Let's make two of them owners. Arbitrarily choose 5 and 7 as the indices.
        owner_indices: list[int] = [5, 7]
        bulk_users: list[User] = []
        bulk_memberships: list[Membership] = []
        for n in range(25):
            if n in owner_indices:
                clone_result = self._clone_user(user, role=Role.OWNER)
            else:
                clone_result = self._clone_user(user)
            bulk_users.append(clone_result.user)
            bulk_memberships.append(clone_result.membership)
        assert bulk_users[0].pk is None, "Pre-condition"
        assert bulk_memberships[0].pk is None, "Pre-condition"  # type: ignore[unreachable]
        User.objects.bulk_create(bulk_users)
        assert bulk_users[0].pk is not None, (
            "Post-condition: Expecting DB to be setting primary keys for us right now. "
            "If you use a different DB that doesn't do that then re-query before "
            "`Membership.objects.bulk_create` and properly set values or do something "
            "else, etc. The `Membership` instances will require the `user` fields to "
            "be persisted."
        )
        Membership.objects.bulk_create(bulk_memberships)
        assert bulk_memberships[0].pk is not None, (
            "Post-condition: See above post-condition string."
        )

        owners = [m for m in bulk_memberships if m.role == Role.OWNER]
        members = [m for m in bulk_memberships if m.role == Role.MEMBER]
        num_owners = len(owners)
        num_members = len(members)

        return BulkCloneUsersResult(
            account=account,
            users=bulk_users,
            memberships=bulk_memberships,
            owners=owners,
            members=members,
            num_owners=num_owners,
            num_members=num_members,
            owner_indices=owner_indices,
        )

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_functionality_with_queryset_annotations_pulled_in(
        self, account_type: AccountType
    ):
        email1 = "ue1@tests.betterbase.com"
        email2 = "ue2@tests.betterbase.com"
        email3 = "ue3@tests.betterbase.com"

        account1: Account = AccountFactory.create(account_type=account_type, name="")
        user1: User = UserFactory.create(
            account=account1,
            membership__role=Role.OWNER,
            created=self._next_now_incremented,
            email=email1,
            name="First Owner Name",
        )
        user2: User = UserFactory.create(
            account=account1,
            membership__role=Role.MEMBER,
            created=self._next_now_incremented,
            email=email2,
            name="First Member Name",
        )
        user3: User = UserFactory.create(
            account=account1,
            membership__role=Role.OWNER,
            created=self._next_now_incremented,
            email=email3,
            name="Second Owner Name",
        )
        m1 = user1._membership_factory_created_  # type: ignore[attr-defined]
        m2 = user2._membership_factory_created_  # type: ignore[attr-defined]
        m3 = user3._membership_factory_created_  # type: ignore[attr-defined]

        assert user3.created > user2.created > user1.created, "Pre-condition"
        assert user1.created == user1.date_joined, "Pre-condition"
        assert user2.created == user2.date_joined, "Pre-condition"
        assert user3.created == user3.date_joined, "Pre-condition"

        bulk_clone_result = self._bulk_clone_users(user2)
        assert bulk_clone_result.num_owners == 2, "Current pre-condition"
        assert bulk_clone_result.num_members == 23, "Current pre-condition"

        # Let's make a few other users to make sure queries aren't incorrectly mixing
        # with other accounts, etc.
        account2 = AccountFactory.create()
        other_user1 = UserFactory.create(
            account=account2,
            membership__role=Role.OWNER,
            created=self.now - timedelta(milliseconds=3),
        )
        other_user2 = UserFactory.create(
            account=account2,
            membership__role=Role.MEMBER,
            created=self.now - timedelta(milliseconds=2),
        )
        assert other_user1.pk is not None, "Pre-condition"
        assert other_user2.pk is not None, "Pre-condition"

        base_qs = (
            Account.objects.all()
            .with_membership_counts_by_role()
            .with_total_memberships_counts()
        )
        qs1 = base_qs.with_all_memberships()
        qs2 = base_qs.with_initial_up_to_25_memberships_by_priority()
        qs3 = base_qs.with_initial_up_to_25_memberships_by_priority().with_all_memberships()

        # 1. Pulling in the `Account`.
        # 2. The `with_all_memberships` `Prefetch`.
        # Everything else should not generate additional queries, and we do some stress
        # testing of it with a `for` loop at the end to be sure.
        with self.django_assert_num_queries(2):
            a1: Account = qs1.get(pk=account1.pk)
            p1 = a1.qs_pulled_in

            assert a1.name == "", "Current pre-condition"
            expected_name1 = (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1} (First Owner Name)"
            )
            assert str(a1) == expected_name1
            assert a1.first_owner == user1
            # Even though we're allowing a DB query it should use the pulled in value
            # instead of querying for a new one which partially contributes to why
            # `self.django_assert_num_queries` above is set to the number that it is.
            assert a1.get_fallback_name(allow_db_query=True) == expected_name1
            assert a1.get_fallback_name(allow_db_query=False) == expected_name1

            assert p1.has_all_memberships is True
            assert p1.all_memberships == [
                *[m1, m3],
                *bulk_clone_result.owners,
                *[m2, *bulk_clone_result.members],
            ]
            assert p1.has_initial_up_to_25_memberships_by_priority is False
            with pytest.raises(AttributeError):
                p1.initial_up_to_25_memberships_by_priority  # noqa: B018
            assert p1.has_membership_counts is True
            assert p1.membership_counts == {
                Role.OWNER: 4,
                Role.MEMBER: 24,
            }
            assert p1.has_total_memberships_count is True
            assert p1.total_memberships_count == 28

            # These should not generate additional queries. Stuff should already be
            # pulled in for `Account`s, `Membership`s, and `User`s.
            for m in p1.all_memberships:
                repr(m.account)
                repr(m.user)
                repr(m)
                str(m.account)
                str(m.user)
                str(m)

        user1.__class__.objects.filter(pk=user1.pk).update(name="")

        # 1. Pulling in the `Account`.
        # 2. The `with_initial_up_to_25_memberships_by_priority` `Prefetch`.
        # Everything else should not generate additional queries, and we do some stress
        # testing of it with a `for` loop at the end to be sure.
        with self.django_assert_num_queries(2):
            a2: Account = qs2.get(pk=account1.pk)
            p2 = a2.qs_pulled_in

            assert a2.name == "", "Current pre-condition"
            expected_name2 = (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1}"
            )
            assert str(a2) == expected_name2
            assert a2.first_owner == user1
            # Even though we're allowing a DB query it should use the pulled in value
            # instead of querying for a new one which partially contributes to why
            # `self.django_assert_num_queries` above is set to the number that it is.
            assert a2.get_fallback_name(allow_db_query=True) == expected_name2
            assert a2.get_fallback_name(allow_db_query=False) == expected_name2

            assert p2.has_all_memberships is False
            with pytest.raises(AttributeError):
                p2.all_memberships  # noqa: B018
            assert p2.has_initial_up_to_25_memberships_by_priority is True
            assert p2.initial_up_to_25_memberships_by_priority == [
                *[m1, m3],
                *bulk_clone_result.owners,
                *[m2, *bulk_clone_result.members[:20]],
            ]
            assert p2.has_membership_counts is True
            assert p2.membership_counts == {
                Role.OWNER: 4,
                Role.MEMBER: 24,
            }
            assert p2.has_total_memberships_count is True
            assert p2.total_memberships_count == 28

            # These should not generate additional queries. Stuff should already be
            # pulled in for `Account`s, `Membership`s, and `User`s.
            for m in p2.initial_up_to_25_memberships_by_priority:
                repr(m.account)
                repr(m.user)
                repr(m)
                str(m.account)
                str(m.user)
                str(m)

        account1.__class__.objects.filter(pk=account1.pk).update(
            name="New Account Name"
        )
        user1.__class__.objects.filter(pk=user1.pk).update(name="First Owner Name")

        # 1. Pulling in the `Account`.
        # 2. with_initial_up_to_25_memberships_by_priority `Prefetch`.
        # 3. The `with_all_memberships` `Prefetch`.
        # Everything else should not generate additional queries, and we do some stress
        # testing of it with a `for` loop at the end to be sure.
        with self.django_assert_num_queries(3):
            a3: Account = qs3.get(pk=account1.pk)
            p3 = a3.qs_pulled_in

            assert a3.name == "New Account Name", "Current pre-condition"
            expected_name3 = f"Account (pk={account1.pk}): New Account Name"
            expected_name3 = (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                "New Account Name"
            )
            assert str(a3) == expected_name3
            assert a3.first_owner == user1
            # Even though we're allowing a DB query it should use the pulled in value
            # instead of querying for a new one which partially contributes to why
            # `self.django_assert_num_queries` above is set to the number that it is.
            assert a3.get_fallback_name(allow_db_query=True) == (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1} (First Owner Name)"
            )
            assert a3.get_fallback_name(allow_db_query=False) == (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1} (First Owner Name)"
            )

            assert p3.has_all_memberships is True
            assert p3.all_memberships == [
                *[m1, m3],
                *bulk_clone_result.owners,
                *[m2, *bulk_clone_result.members],
            ]
            assert p3.has_initial_up_to_25_memberships_by_priority is True
            assert p3.initial_up_to_25_memberships_by_priority == [
                *[m1, m3],
                *bulk_clone_result.owners,
                *[m2, *bulk_clone_result.members[:20]],
            ]
            assert p3.has_membership_counts is True
            assert p3.membership_counts == {
                Role.OWNER: 4,
                Role.MEMBER: 24,
            }
            assert p3.has_total_memberships_count is True
            assert p3.total_memberships_count == 28

            # These should not generate additional queries. Stuff should already be
            # pulled in for `Account`s, `Membership`s, and `User`s.
            for m in p3.all_memberships:
                repr(m.account)
                repr(m.user)
                repr(m)
                str(m.account)
                str(m.user)
                str(m)

    @pytest.mark.parametrize("account_type", [*AccountType])
    def test_functionality_with_no_queryset_annotations_pulled_in(
        self, account_type: AccountType
    ):
        email1 = "ue1@tests.betterbase.com"
        email2 = "ue2@tests.betterbase.com"
        email3 = "ue3@tests.betterbase.com"

        account1 = AccountFactory.create(account_type=account_type, name="")
        user1 = UserFactory.create(
            account=account1,
            membership__role=Role.OWNER,
            created=self._next_now_incremented,
            email=email1,
            name="First Owner Name",
        )
        user2 = UserFactory.create(
            account=account1,
            membership__role=Role.MEMBER,
            created=self._next_now_incremented,
            email=email2,
            name="First Member Name",
        )
        user3 = UserFactory.create(
            account=account1,
            membership__role=Role.OWNER,
            created=self._next_now_incremented,
            email=email3,
            name="Second Owner Name",
        )

        assert user3.created > user2.created > user1.created, "Pre-condition"
        assert user1.created == user1.date_joined, "Pre-condition"
        assert user2.created == user2.date_joined, "Pre-condition"
        assert user3.created == user3.date_joined, "Pre-condition"

        bulk_clone_result = self._bulk_clone_users(user2)
        assert bulk_clone_result.num_owners == 2, "Current pre-condition"
        assert bulk_clone_result.num_members == 23, "Current pre-condition"

        # Let's make a few other users to make sure queries aren't incorrectly mixing
        # with other accounts, etc.
        account2 = AccountFactory.create()
        other_user1 = UserFactory.create(
            account=account2,
            membership__role=Role.OWNER,
            created=self.now - timedelta(milliseconds=3),
        )
        other_user2 = UserFactory.create(
            account=account2,
            membership__role=Role.MEMBER,
            created=self.now - timedelta(milliseconds=2),
        )
        assert other_user1.pk is not None, "Pre-condition"
        assert other_user2.pk is not None, "Pre-condition"

        def _assert_not_pulled_in(a: Account) -> None:
            p = a.qs_pulled_in

            assert p.has_all_memberships is False
            with pytest.raises(AttributeError):
                p.all_memberships  # noqa: B018
            assert p.has_initial_up_to_25_memberships_by_priority is False
            with pytest.raises(AttributeError):
                p.initial_up_to_25_memberships_by_priority  # noqa: B018
            assert p.has_membership_counts is False
            with pytest.raises(AttributeError):
                p.membership_counts  # noqa: B018
            assert p.has_total_memberships_count is False
            with pytest.raises(AttributeError):
                p.total_memberships_count  # noqa: B018

        # 1. Pulling in the `Account`.
        # 2. `a1.get_fallback_name(allow_db_query=True)`.
        # Everything else should not generate additional queries.
        with self.django_assert_num_queries(2):
            a1 = Account.objects.get(pk=account1.pk)
            assert a1.name == "", "Current pre-condition"
            expected_name1 = (
                f"Account (pk={account1.pk}, account_type={account_type}): Unnamed"
            )
            assert str(a1) == expected_name1
            assert a1.first_owner == user1
            assert a1.get_fallback_name(allow_db_query=True) == (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1} (First Owner Name)"
            )
            assert a1.get_fallback_name(allow_db_query=False) == expected_name1
            _assert_not_pulled_in(a1)

        user1.__class__.objects.filter(pk=user1.pk).update(name="")

        # 1. Pulling in the `Account`.
        # 2. `a2.get_fallback_name(allow_db_query=True)`.
        # Everything else should not generate additional queries.
        with self.django_assert_num_queries(2):
            a2 = Account.objects.get(pk=account1.pk)
            assert a2.name == "", "Current pre-condition"
            expected_name2 = (
                f"Account (pk={account1.pk}, account_type={account_type}): Unnamed"
            )
            assert str(a2) == expected_name2
            assert a2.first_owner == user1
            assert a2.get_fallback_name(allow_db_query=True) == (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1}"
            )
            assert a2.get_fallback_name(allow_db_query=False) == expected_name2
            _assert_not_pulled_in(a2)

        account1.__class__.objects.filter(pk=account1.pk).update(
            name="New Account Name"
        )
        user1.__class__.objects.filter(pk=user1.pk).update(name="First Owner Name")

        # 1. Pulling in the `Account`.
        # 2. `a3.get_fallback_name(allow_db_query=True)`.
        # Everything else should not generate additional queries.
        with self.django_assert_num_queries(2):
            a3 = Account.objects.get(pk=account1.pk)
            assert a3.name == "New Account Name", "Current pre-condition"
            expected_name3 = (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                "New Account Name"
            )
            assert str(a3) == expected_name3
            assert a3.first_owner == user1
            assert a3.get_fallback_name(allow_db_query=True) == (
                f"Account (pk={account1.pk}, account_type={account_type}): "
                f"First Owner - {email1} (First Owner Name)"
            )
            assert a3.get_fallback_name(allow_db_query=False) == (
                f"Account (pk={account1.pk}, account_type={account_type}): Unnamed"
            )
            _assert_not_pulled_in(a3)
