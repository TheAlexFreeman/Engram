from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime, timedelta
from operator import attrgetter
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import ImageField as DjangoFormsImageField

from backend.accounts.models import Account, Membership, User
from backend.accounts.ops.uploaded_images import (
    UserUpdateUploadedProfileImageFailedResult,
    UserUpdateUploadedProfileImageSuccessResult,
)
from backend.accounts.ops.users import (
    DELETE_ACCOUNT,
    DELETE_MEMBERSHIP,
    NOTIFY_OTHER_OWNERS,
    OTHER_MEMBERS,
    OTHER_OWNERS,
    TRANSFER_OWNERSHIP,
    CheckUserDeletionOps,
    delete_uploaded_profile_image,
    delete_user,
    update_uploaded_profile_image,
)
from backend.accounts.tests.factories import (
    AccountFactory,
    MembershipFactory,
    UserFactory,
)
from backend.accounts.tests.factories.users import (
    SKIP_ACCOUNT_CREATION,
    SKIP_MEMBERSHIP_CREATION,
)
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.images import create_test_image
from backend.utils.fixture_serialization import (
    serialize_one_model_instance_to_json_dict,
)


@pytest.fixture
def other_accounts_and_memberships_and_users():
    """
    Data that, for example, should not be touched when `delete_user` is called, etc.

    Ultimately, allows tests using this data to assert that their operations did not
    affect this data, which means that the operations are properly scoped to the
    `Account`(s), `User`(s), and/or `Membership`(s), etc., that they should be without
    accidentally affecting other data.
    """
    accounts: list[Account] = []
    memberships: list[Membership] = []
    users: list[User] = []

    u1 = UserFactory.create()
    a1 = u1._account_factory_created_
    m1 = u1._membership_factory_created_
    assert u1._account_ == m1.account, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"

    a2 = AccountFactory.create()
    u2 = UserFactory.create(account=a2, membership__role=Role.OWNER)
    u3 = UserFactory.create(account=a2, membership__role=Role.MEMBER)
    u4 = UserFactory.create(account=a2, membership__role=Role.OWNER)
    m2 = u2._membership_factory_created_
    m3 = u3._membership_factory_created_
    m4 = u4._membership_factory_created_

    a3 = AccountFactory.create()
    u5 = UserFactory.create(account=a3, membership=SKIP_MEMBERSHIP_CREATION)
    u6 = UserFactory.create(account=a3, membership=SKIP_MEMBERSHIP_CREATION)
    m5 = MembershipFactory.create(account=a3, user=u5)
    assert m5.role == Role.OWNER, "Pre-condition"
    m6 = MembershipFactory.create(account=a3, user=u6, role=Role.MEMBER)

    accounts.append(a1)
    accounts.append(a2)
    accounts.append(a3)
    memberships.append(m1)
    memberships.append(m2)
    memberships.append(m3)
    memberships.append(m4)
    memberships.append(m5)
    memberships.append(m6)
    users.append(u1)
    users.append(u2)
    users.append(u3)
    users.append(u4)
    users.append(u5)
    users.append(u6)

    accounts = sorted(accounts, key=lambda v: v.pk)
    memberships = sorted(memberships, key=lambda v: v.pk)
    users = sorted(users, key=lambda v: v.pk)

    convert = serialize_one_model_instance_to_json_dict
    original_data = {
        "accounts": list(map(convert, accounts)),
        "memberships": list(map(convert, memberships)),
        "users": list(map(convert, users)),
    }

    def assert_not_touched():
        updated_accounts: list[Account] = list(
            Account.objects.filter(pk__in=[a.pk for a in accounts]).order_by("pk")
        )
        updated_memberships: list[Membership] = list(
            Membership.objects.filter(pk__in=[m.pk for m in memberships]).order_by("pk")
        )
        updated_users: list[User] = list(
            User.objects.filter(pk__in=[u.pk for u in users]).order_by("pk")
        )

        updated_accounts = sorted(updated_accounts, key=lambda v: v.pk)
        updated_memberships = sorted(updated_memberships, key=lambda v: v.pk)
        updated_users = sorted(updated_users, key=lambda v: v.pk)

        updated_data = {
            "accounts": list(map(convert, updated_accounts)),
            "memberships": list(map(convert, updated_memberships)),
            "users": list(map(convert, updated_users)),
        }

        assert original_data == updated_data

    return {
        "accounts": accounts,
        "memberships": memberships,
        "users": users,
        "assert_not_touched": assert_not_touched,
    }


@pytest.mark.django_db
class TestDeleteUserOps:
    """
    At the time of writing, this tests `CheckUserDeletionOps.check` and `delete_user`.
    """

    @pytest.fixture(autouse=True)
    def setup(self, other_accounts_and_memberships_and_users) -> None:
        self.other_data = other_accounts_and_memberships_and_users
        self.assert_other_data_not_touched = self.other_data["assert_not_touched"]

    def assert_other_users_and_memberships_not_deleted(
        self, users: list[User], memberships: list[Membership]
    ):
        membership_users = [m.user for m in memberships]

        for m in memberships:
            assert m.pk is not None, "Pre-condition"
        for u in users:
            assert u.pk is not None, "Pre-condition"
        assert sorted([u.pk for u in users]) == sorted(
            [u.pk for u in membership_users]
        ), "Pre-condition"

        assert Membership.objects.filter(
            pk__in=[m.pk for m in memberships]
        ).count() == len(memberships)
        assert User.objects.filter(pk__in=[u.pk for u in users]).count() == len(users)

    def test_delete_all_together(self, now: datetime):
        """
        Big integration test that should hit all of the major (and even some minor, lol)
        code paths.
        """
        start_dt = now - timedelta(milliseconds=60)
        _next_dt_counter: int = 0

        def next_dt():
            nonlocal _next_dt_counter
            _next_dt_counter += 1

            return start_dt + timedelta(milliseconds=_next_dt_counter)

        def model_sort(
            instances: list[Account] | tuple[Account, ...],
            cast: type[list] | type[tuple] = tuple,
        ):
            def sorter(v: Account):
                return (-1 if v.pk is None else v.pk, v.created)

            return cast(sorted(instances, key=sorter))

        a1 = AccountFactory.build(created=next_dt())
        a2 = AccountFactory.build(created=next_dt())
        a3 = AccountFactory.build(created=next_dt())
        a4 = AccountFactory.build(created=next_dt())
        a5 = AccountFactory.build(created=next_dt())
        a6 = AccountFactory.build(created=next_dt())
        a7 = AccountFactory.build(created=next_dt())
        a8 = AccountFactory.build(created=next_dt())
        a9 = AccountFactory.build(created=next_dt())
        a10 = AccountFactory.build(created=next_dt())
        a11 = AccountFactory.build(created=next_dt())

        Account.objects.bulk_create([a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11])
        assert a1.pk is not None, "Current post-condition"
        assert a11.pk is not None, "Current post-condition"
        assert (
            len(
                {
                    a1.created,
                    a2.created,
                    a3.created,
                    a4.created,
                    a5.created,
                    a6.created,
                    a7.created,
                    a8.created,
                    a9.created,
                    a10.created,
                    a11.created,
                }
            )
            == 11
        ), "Current post-condition"

        u_created_at = next_dt()
        u = UserFactory.create(
            account=SKIP_ACCOUNT_CREATION,
            membership=SKIP_MEMBERSHIP_CREATION,
            created=u_created_at,
        )
        reached_end: int = 0

        def assert_grouping_matches(
            g: tuple[Account, ...], expected: tuple[Account, ...]
        ):
            g_created = sorted(map(attrgetter("created"), g))
            expected_created = sorted(map(attrgetter("created"), expected))

            assert len(g_created) == len(expected_created)
            assert len(set(g_created)) == len(set(expected_created))
            assert len(set(g_created)) == len(g_created), "Current post-condition"
            assert len(set(expected_created)) == len(expected_created), (
                "Current post-condition"
            )

        def solo_owned_with_no_other_memberships_checker():
            nonlocal reached_end

            # Setup Phase
            u_m1 = MembershipFactory.create(account=a1, user=u, role=Role.OWNER)
            u_m11 = MembershipFactory.create(account=a11, user=u, role=Role.OWNER)
            u_m2 = MembershipFactory.create(account=a2, user=u, role=Role.OWNER)

            assert u_m1.pk is not None, "Pre-condition"
            assert u_m1.account_id is not None, "Pre-condition"
            assert u_m11.pk is not None, "Pre-condition"
            assert u_m11.account_id is not None, "Pre-condition"
            assert u_m2.pk is not None, "Pre-condition"
            assert u_m2.account_id is not None, "Pre-condition"

            # Post Check Phase
            yield

            assert model_sort(
                cr.account_groupings.solo_owned_with_no_other_memberships
            ) == model_sort((a1, a11, a2))
            assert cr.automated_actions_planned[a1] == DELETE_ACCOUNT
            assert cr.automated_actions_planned[a11] == DELETE_ACCOUNT
            assert cr.automated_actions_planned[a2] == DELETE_ACCOUNT

            # Post Delete Phase
            yield

            assert a1.pk is not None, "Current post-condition"
            assert a11.pk is not None, "Current post-condition"
            assert a2.pk is not None, "Current post-condition"
            assert u_m1.account_id is not None, "Current post-condition"
            assert u_m11.account_id is not None, "Current post-condition"
            assert u_m2.account_id is not None, "Current post-condition"
            assert u_m1.pk is not None, "Current post-condition"
            assert u_m11.pk is not None, "Current post-condition"
            assert u_m2.pk is not None, "Current post-condition"

            assert (
                Account.objects.filter(
                    pk__in=[
                        a1.pk,
                        a11.pk,
                        a2.pk,
                        u_m1.account_id,
                        u_m11.account_id,
                        u_m2.account_id,
                    ]
                ).count()
                == 0
            )
            assert (
                Membership.objects.filter(pk__in=[u_m1.pk, u_m11.pk, u_m2.pk]).count()
                == 0
            )
            assert_grouping_matches(
                fcr.account_groupings.solo_owned_with_no_other_memberships,
                (a1, a11, a2),
            )

            reached_end += 1

        def solo_owned_with_other_memberships_checker():
            nonlocal reached_end

            # Setup Phase
            u_m3 = MembershipFactory.create(account=a3, user=u, role=Role.OWNER)
            u_m4 = MembershipFactory.create(account=a4, user=u, role=Role.OWNER)

            o_a3_u1 = UserFactory.create(account=a3, membership__role=Role.MEMBER)
            o_a3_m1 = o_a3_u1._membership_factory_created_
            o_a3_u2 = UserFactory.create(account=a3, membership__role=Role.MEMBER)
            o_a3_m2 = o_a3_u2._membership_factory_created_
            o_a4_u1 = UserFactory.create(account=a4, membership__role=Role.MEMBER)
            o_a4_m1 = o_a4_u1._membership_factory_created_

            assert u_m3.pk is not None, "Pre-condition"
            assert u_m3.account_id is not None, "Pre-condition"
            assert o_a3_u1.pk is not None, "Pre-condition"
            assert o_a3_m1.account_id is not None, "Pre-condition"
            assert o_a3_m1.user_id is not None, "Pre-condition"

            # Post Check Phase
            yield

            assert model_sort(
                cr.account_groupings.solo_owned_with_other_memberships
            ) == model_sort((a3, a4))
            assert cr.automated_actions_planned[a3] == DELETE_ACCOUNT
            assert cr.automated_actions_planned[a4] == DELETE_ACCOUNT

            # Post Delete Phase
            yield

            assert a3.pk is not None, "Current post-condition"
            assert a4.pk is not None, "Current post-condition"
            assert u_m3.account_id is not None, "Current post-condition"
            assert u_m4.account_id is not None, "Current post-condition"
            assert o_a3_m1.account_id is not None, "Current post-condition"
            assert o_a3_m2.account_id is not None, "Current post-condition"
            assert o_a4_m1.account_id is not None, "Current post-condition"
            assert u_m3.pk is not None, "Current post-condition"
            assert u_m4.pk is not None, "Current post-condition"
            assert o_a3_m1.pk is not None, "Current post-condition"
            assert o_a3_m2.pk is not None, "Current post-condition"
            assert o_a4_m1.pk is not None, "Current post-condition"

            assert (
                Account.objects.filter(
                    pk__in=[
                        a3.pk,
                        a4.pk,
                        u_m3.account_id,
                        u_m4.account_id,
                        o_a3_m1.account_id,
                        o_a3_m2.account_id,
                        o_a4_m1.account_id,
                    ]
                ).count()
                == 0
            )
            assert (
                Membership.objects.filter(
                    pk__in=[
                        u_m3.pk,
                        u_m4.pk,
                        o_a3_m1.pk,
                        o_a3_m2.pk,
                        o_a4_m1.pk,
                    ]
                ).count()
                == 0
            )
            assert_grouping_matches(
                fcr.account_groupings.solo_owned_with_other_memberships, (a3, a4)
            )

            reached_end += 1

        def jointly_owned_checker():
            nonlocal reached_end

            # Setup Phase
            u_m5 = MembershipFactory.create(account=a5, user=u, role=Role.OWNER)
            u_m6 = MembershipFactory.create(account=a6, user=u, role=Role.OWNER)

            o_a5_u1 = UserFactory.create(account=a5, membership__role=Role.OWNER)
            o_a5_m1 = o_a5_u1._membership_factory_created_
            o_a5_u2 = UserFactory.create(account=a5, membership__role=Role.MEMBER)
            o_a5_m2 = o_a5_u2._membership_factory_created_
            o_a6_u1 = UserFactory.create(account=a6, membership__role=Role.OWNER)
            o_a6_m1 = o_a6_u1._membership_factory_created_

            # Post Check Phase
            yield

            assert model_sort(cr.account_groupings.jointly_owned) == model_sort(
                (a5, a6)
            )
            assert cr.automated_actions_planned[a5] == DELETE_MEMBERSHIP
            assert cr.automated_actions_planned[a6] == DELETE_MEMBERSHIP

            # Post Delete Phase
            yield

            assert sorted(
                Account.objects.filter(
                    pk__in=[
                        a5.pk,
                        a6.pk,
                        u_m5.account_id,
                        u_m6.account_id,
                        o_a5_m1.account_id,
                        o_a5_m2.account_id,
                        o_a6_m1.account_id,
                    ]
                ).values_list("pk", flat=True)
            ) == sorted([a5.pk, a6.pk])
            assert sorted(
                Membership.objects.filter(
                    pk__in=[
                        u_m5.pk,
                        u_m6.pk,
                        o_a5_m1.pk,
                        o_a5_m2.pk,
                        o_a6_m1.pk,
                    ]
                ).values_list("pk", flat=True)
            ) == sorted([o_a5_m1.pk, o_a5_m2.pk, o_a6_m1.pk])
            assert_grouping_matches(fcr.account_groupings.jointly_owned, (a5, a6))

            reached_end += 1

        def not_owner_in_checker():
            nonlocal reached_end

            # Setup Phase
            o_a7_u1 = UserFactory.create(account=a7, membership__role=Role.OWNER)
            o_a7_m1 = o_a7_u1._membership_factory_created_
            o_a7_u2 = UserFactory.create(account=a7, membership__role=Role.MEMBER)
            o_a7_m2 = o_a7_u2._membership_factory_created_
            o_a8_u1 = UserFactory.create(account=a8, membership__role=Role.OWNER)
            o_a8_m1 = o_a8_u1._membership_factory_created_

            u_m7 = MembershipFactory.create(account=a7, user=u, role=Role.MEMBER)
            u_m8 = MembershipFactory.create(account=a8, user=u, role=Role.MEMBER)

            # Post Check Phase
            yield

            assert model_sort(cr.account_groupings.not_owner_in) == model_sort((a7, a8))
            assert cr.automated_actions_planned[a7] == DELETE_MEMBERSHIP
            assert cr.automated_actions_planned[a8] == DELETE_MEMBERSHIP

            # Post Delete Phase
            yield
            assert sorted(
                Account.objects.filter(
                    pk__in=[
                        a7.pk,
                        a8.pk,
                        o_a7_m1.account_id,
                        o_a7_m2.account_id,
                        o_a8_m1.account_id,
                    ]
                ).values_list("pk", flat=True)
            ) == sorted([a7.pk, a8.pk])
            assert sorted(
                Membership.objects.filter(
                    pk__in=[
                        u_m7.pk,
                        u_m8.pk,
                        o_a7_m1.pk,
                        o_a7_m2.pk,
                        o_a8_m1.pk,
                    ]
                ).values_list("pk", flat=True)
            ) == sorted([o_a7_m1.pk, o_a7_m2.pk, o_a8_m1.pk])
            assert_grouping_matches(fcr.account_groupings.not_owner_in, (a7, a8))

            reached_end += 1

        def other_checker():
            """
            NOTE: At the time of writing, it's impossible to get to the `else` branch
            that populates `other`. It didn't feel worth it to try and mock or patch the
            code to generate that error condition, so we'll just assert all the `other`
            state is empty.
            """
            nonlocal reached_end

            # Setup Phase
            pass

            # Post Check Phase
            yield

            assert cr.account_groupings.other == ()

            # Post Delete Phase
            yield

            assert sorted(
                Account.objects.filter(pk__in=[a9.pk, a10.pk]).values_list(
                    "pk", flat=True
                )
            ) == sorted([a9.pk, a10.pk])
            assert fcr.account_groupings.other == ()

            reached_end += 1

        checkers = [
            solo_owned_with_no_other_memberships_checker(),
            solo_owned_with_other_memberships_checker(),
            jointly_owned_checker(),
            not_owner_in_checker(),
            other_checker(),
        ]
        for c in checkers:
            next(c)

        # Initial Check result
        cr = CheckUserDeletionOps(u).check()

        for c in checkers:
            next(c)

        assert reached_end == 0, "Pre-condition"

        assert isinstance(cr.user, User)
        assert cr.user.created == u_created_at
        assert cr.user == u
        assert len(cr.memberships) == 9
        assert cr.can_delete_user is True
        assert cr.should_offer_manual_actions_before_deleting is True
        assert (
            sum(
                len(v)
                for v in (
                    getattr(cr.account_groupings, field.name)
                    for field in fields(cr.account_groupings)
                )
            )
            == 9
        )
        assert cr.automated_actions_planned == {
            a1: DELETE_ACCOUNT,
            a11: DELETE_ACCOUNT,
            a2: DELETE_ACCOUNT,
            a3: DELETE_ACCOUNT,
            a4: DELETE_ACCOUNT,
            a5: DELETE_MEMBERSHIP,
            a6: DELETE_MEMBERSHIP,
            a7: DELETE_MEMBERSHIP,
            a8: DELETE_MEMBERSHIP,
        }
        assert cr.manual_actions_required == {}
        assert cr.manual_actions_offered == {
            a3: {OTHER_MEMBERS: [TRANSFER_OWNERSHIP]},
            a4: {OTHER_MEMBERS: [TRANSFER_OWNERSHIP]},
            a5: {OTHER_OWNERS: [DELETE_ACCOUNT, NOTIFY_OTHER_OWNERS]},
            a6: {OTHER_OWNERS: [DELETE_ACCOUNT, NOTIFY_OTHER_OWNERS]},
        }
        assert model_sort(cr.accounts_all_cleared) == model_sort((a1, a11, a2, a7, a8))

        # Deletion result
        dr = delete_user(u)
        # Final Check result
        fcr = dr.check_result

        for c in checkers:
            try:
                next(c)
            except StopIteration:
                pass

        assert reached_end == 5, "Pre-condition"

        self.assert_other_data_not_touched()
        self.assert_other_users_and_memberships_not_deleted(
            self.other_data["users"],
            self.other_data["memberships"],
        )

        assert isinstance(fcr.user, User)
        assert fcr.user.created == u_created_at
        assert len(fcr.memberships) == 9
        assert fcr.can_delete_user is True
        assert fcr.should_offer_manual_actions_before_deleting is True
        assert (
            sum(
                len(v)
                for v in (
                    getattr(fcr.account_groupings, field.name)
                    for field in fields(fcr.account_groupings)
                )
            )
            == 9
        )
        assert len(list(fcr.automated_actions_planned.keys())) == 9
        assert len(list(fcr.manual_actions_required.keys())) == 0
        assert len(list(fcr.manual_actions_offered.keys())) == 4
        assert len(fcr.accounts_all_cleared) == 5


def _make_test_image(
    filename: str, *, r: int, g: int, b: int, size_x: int = 128, size_y: int = 128
):
    """Helper to create an uploaded image suitable for the profile image ops."""
    image_file = create_test_image(
        filename, r=r, g=g, b=b, size_x=size_x, size_y=size_y
    )
    image_file.seek(0)
    assert image_file, "Pre-condition"

    simple_uploaded_file = SimpleUploadedFile(
        name=image_file.name,  # type: ignore[arg-type]
        content=image_file.read(),
        content_type="image/png",
    )
    image_file.seek(0)
    simple_uploaded_file.seek(0)
    assert simple_uploaded_file, "Pre-condition"

    uploaded_image = DjangoFormsImageField().clean(simple_uploaded_file)
    assert uploaded_image, "Pre-condition"

    return uploaded_image


@contextmanager
def _patch_user_profile_image_delete_logger() -> Generator[MagicMock]:
    """
    Patches the `logger.exception` call inside `User._try_and_delete_profile_image`.

    Both the happy-path tests (`assert_not_called`) and the negative/crash tests
    (`assert_called_once`) use this same helper so the patch target is defined in
    one place. If the implementation moves the logger, fixing this helper fixes
    every test that depends on it.
    """
    with patch("backend.accounts.models.users.logger.exception") as mock_log_exc:
        yield mock_log_exc


@pytest.mark.django_db
def test_user_update_and_delete_uploaded_profile_image():
    """
    Tests the full lifecycle of a `User`'s profile image: upload, replace, and delete.
    Verifies that the `FieldTracker`'s `LightStateFieldFile` (which has `instance=None`)
    does not cause an `AttributeError` during the delete or replace flows.
    """
    u = UserFactory.create()
    assert not u.uploaded_profile_image, "Pre-condition"
    storage = u._meta.get_field("uploaded_profile_image").storage

    # Upload an image.
    img1 = _make_test_image("user-test-image1.png", r=100, g=101, b=102)
    result1 = update_uploaded_profile_image(u, img1)
    assert isinstance(result1, UserUpdateUploadedProfileImageSuccessResult)
    assert result1.user == u

    u.refresh_from_db()
    assert u.uploaded_profile_image
    img1.seek(0)
    assert u.uploaded_profile_image.read() == img1.read()
    i1_name = u.uploaded_profile_image.name
    assert i1_name is not None
    assert storage.exists(i1_name)

    img1.close()
    u.uploaded_profile_image.close()

    # Replace with a second image; the first should be cleaned up from storage.
    img2 = _make_test_image("user-test-image2.png", r=110, g=111, b=112)
    with _patch_user_profile_image_delete_logger() as mock_log_exc:
        result2 = update_uploaded_profile_image(u, img2)
        # The save-time tracker cleanup must not hit the exception path.
        mock_log_exc.assert_not_called()

    assert isinstance(result2, UserUpdateUploadedProfileImageSuccessResult)

    u.refresh_from_db()
    assert u.uploaded_profile_image
    i2_name = u.uploaded_profile_image.name
    assert i2_name is not None
    assert storage.exists(i2_name)
    assert not storage.exists(i1_name), "Old image should have been removed."

    img2.close()
    u.uploaded_profile_image.close()

    # Delete via the op. This is the exact flow that triggered the original bug:
    # `delete_uploaded_profile_image` calls `.delete(save=False)` then `.save()`,
    # and the `save()` sees a tracker diff and tries to delete the previous
    # `LightStateFieldFile` which has `instance=None`.
    with _patch_user_profile_image_delete_logger() as mock_log_exc:
        delete_uploaded_profile_image(u)
        mock_log_exc.assert_not_called()

    u.refresh_from_db()
    assert not u.uploaded_profile_image
    assert not storage.exists(i2_name)

    # Upload again after delete to confirm clean round-trip.
    img3 = _make_test_image("user-test-image3.png", r=120, g=121, b=122)
    result3 = update_uploaded_profile_image(u, img3)
    assert isinstance(result3, UserUpdateUploadedProfileImageSuccessResult)

    u.refresh_from_db()
    assert u.uploaded_profile_image
    i3_name = u.uploaded_profile_image.name
    assert i3_name is not None
    assert storage.exists(i3_name)

    img3.close()
    u.uploaded_profile_image.close()

    # Delete the user entirely; the image should be cleaned up.
    u.delete()
    assert not storage.exists(i3_name)


@pytest.mark.django_db
def test_user_update_uploaded_profile_image_failure_paths():
    """Tests validation failures for `User` profile image uploads."""
    u = UserFactory.create()

    # Missing `.image` attribute.
    img_missing = _make_test_image(
        "user-test-fail1.png", r=127, g=128, b=129, size_x=128, size_y=128
    )
    del img_missing.image
    result_missing = update_uploaded_profile_image(u, img_missing)
    assert isinstance(result_missing, UserUpdateUploadedProfileImageFailedResult)
    assert result_missing.code == "invalid"

    # Dimensions too large.
    img_too_large = _make_test_image(
        "user-test-fail2.png", r=128, g=129, b=130, size_x=1_025, size_y=1_025
    )
    result_too_large = update_uploaded_profile_image(u, img_too_large)
    assert isinstance(result_too_large, UserUpdateUploadedProfileImageFailedResult)
    assert result_too_large.code == "invalid_dimensions"

    # File size too big.
    img_size_too_big = _make_test_image(
        "user-test-fail3.png", r=128, g=129, b=130, size_x=128, size_y=128
    )
    img_size_too_big.size = 3_000_001
    result_size_too_big = update_uploaded_profile_image(u, img_size_too_big)
    assert isinstance(result_size_too_big, UserUpdateUploadedProfileImageFailedResult)
    assert result_size_too_big.code == "invalid_file_size"
    assert result_size_too_big.message == "The file size can be at most 3.0 MB."

    # Valid upload should still succeed after failures.
    img_valid = _make_test_image(
        "user-test-valid.png", r=130, g=131, b=132, size_x=512, size_y=512
    )
    result_valid = update_uploaded_profile_image(u, img_valid)
    assert isinstance(result_valid, UserUpdateUploadedProfileImageSuccessResult)


@pytest.mark.django_db
def test_user_profile_image_storage_failure_logs_exception():
    """
    Intentionally breaks storage deletion to verify that `logger.exception` is
    actually called with the expected message and kwargs. This confirms that the
    `assert_not_called` checks in the happy-path tests are patching the correct
    target — if the patch target were wrong, this test would fail because the mock
    would never be called.
    """
    u = UserFactory.create()
    storage = u._meta.get_field("uploaded_profile_image").storage

    # Upload an initial image so there's something for the tracker to detect.
    img1 = _make_test_image("user-crash-1.png", r=200, g=0, b=0)
    update_uploaded_profile_image(u, img1)
    u.refresh_from_db()
    assert u.uploaded_profile_image, "Pre-condition"

    # Replace with a second image, but sabotage `storage.delete` so the cleanup
    # of the old image fails. The `update_uploaded_profile_image` op calls
    # `FieldFile.save()` (which uses `storage.save`, not `storage.delete`), then
    # `Model.save()` detects the tracker diff and calls `_try_and_delete_profile_image`
    # which calls `storage.delete` — that's the call we're breaking.
    img2 = _make_test_image("user-crash-2.png", r=0, g=200, b=0)
    with (
        patch.object(
            storage, "delete", side_effect=OSError("Simulated storage failure")
        ),
        _patch_user_profile_image_delete_logger() as mock_log_exc,
    ):
        # The op should still succeed — the cleanup failure is caught and logged.
        result = update_uploaded_profile_image(u, img2)
        assert isinstance(result, UserUpdateUploadedProfileImageSuccessResult)

        mock_log_exc.assert_called_once()
        log_message = mock_log_exc.call_args[0][0]
        log_kwargs = mock_log_exc.call_args[1]

        assert "User" in log_message
        assert "profile image" in log_message
        assert log_kwargs["user_pk"] == u.pk
        assert log_kwargs["user_email"] == u.email
        assert log_kwargs["did_just_delete_user"] is False
