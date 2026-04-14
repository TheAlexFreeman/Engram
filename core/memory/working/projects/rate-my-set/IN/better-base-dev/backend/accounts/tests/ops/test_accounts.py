from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import ImageField as DjangoFormsImageField

from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.memberships import Membership
from backend.accounts.ops.accounts import (
    create_account,
    create_personal_account,
    create_team_account,
    delete_account,
    delete_uploaded_profile_image,
    update_account,
    update_account_type,
    update_uploaded_profile_image,
)
from backend.accounts.ops.memberships import create_membership
from backend.accounts.ops.uploaded_images import (
    AccountUpdateUploadedProfileImageFailedResult,
    AccountUpdateUploadedProfileImageSuccessResult,
)
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.images import create_test_image


@pytest.mark.django_db
def test_create_personal_account():
    u1 = UserFactory.create(
        account__account_type=AccountType.TEAM, membership__role=Role.OWNER
    )
    m1 = Membership.objects.get(user=u1)
    assert m1.user == u1, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"
    assert m1.account.account_type == AccountType.TEAM, "Pre-condition"

    a2 = create_personal_account(name="")
    a3 = create_personal_account(name="Some Account")
    a4 = create_account(account_type=AccountType.PERSONAL, name="")
    a5 = create_account(account_type=AccountType.PERSONAL, name="Some Account")

    assert a2.name == "Personal Account"
    assert a2.account_type == AccountType.PERSONAL
    assert a2.pk is not None

    assert a3.name == "Some Account"
    assert a3.account_type == AccountType.PERSONAL
    assert a3.pk is not None

    assert a4.name == "Personal Account"
    assert a4.account_type == AccountType.PERSONAL
    assert a4.pk is not None

    assert a5.name == "Some Account"
    assert a5.account_type == AccountType.PERSONAL
    assert a5.pk is not None

    assert u1.memberships.count() == 1


@pytest.mark.django_db
def test_create_team_account():
    u1 = UserFactory.create(account__account_type=AccountType.PERSONAL)
    m1 = Membership.objects.get(user=u1)
    assert m1.user == u1, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"
    assert m1.account.account_type == AccountType.PERSONAL, "Pre-condition"

    a1 = create_team_account(name="")
    a2 = create_team_account(name="Some Account")
    a3 = create_account(account_type=AccountType.TEAM, name="")
    a4 = create_account(account_type=AccountType.TEAM, name="Some Account")

    assert a1.name == "Team Account"
    assert a1.account_type == AccountType.TEAM
    assert a1.pk is not None

    assert a2.name == "Some Account"
    assert a2.account_type == AccountType.TEAM
    assert a2.pk is not None

    assert a3.name == "Team Account"
    assert a3.account_type == AccountType.TEAM
    assert a3.pk is not None

    assert a4.name == "Some Account"
    assert a4.account_type == AccountType.TEAM
    assert a4.pk is not None

    assert u1.memberships.count() == 1


@pytest.mark.django_db
def test_update_account():
    a1 = create_personal_account(name="Personal Account 1")
    a2 = create_team_account(name="Team Account 1")

    assert a1.name == "Personal Account 1"
    assert a2.name == "Team Account 1"

    update_account(a1, name="Personal Account 2")
    update_account(a2, name="Team Account 2")

    assert a1.name == "Personal Account 2"
    assert a2.name == "Team Account 2"

    update_account(a1, name="")
    update_account(a2, name="")

    assert a1.name == "Personal Account"
    assert a2.name == "Team Account"


@pytest.mark.django_db
def test_update_account_type_from_team_to_personal():
    u1 = UserFactory.create(
        account__account_type=AccountType.TEAM, membership__role=Role.OWNER
    )
    m1 = Membership.objects.get(user=u1)
    assert m1.user == u1, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"
    assert m1.account.account_type == AccountType.TEAM, "Pre-condition"
    a1 = m1.account

    with pytest.raises(
        NotImplementedError,
        match=(
            r"At the time of writing, we don't have an implementation for "
            r"downgrading an account from a non-personal account to a personal account."
        ),
    ):
        update_account_type(a1, new_account_type=AccountType.PERSONAL)

    a1.refresh_from_db()
    assert a1.account_type == AccountType.TEAM

    update_account_type(a1, new_account_type=AccountType.TEAM)

    a1.refresh_from_db()
    assert a1.account_type == AccountType.TEAM


@pytest.mark.django_db
def test_update_account_type_from_personal_to_team():
    u1 = UserFactory.create(
        account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
    )
    m1 = Membership.objects.get(user=u1)
    assert m1.user == u1, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"
    assert m1.account.account_type == AccountType.PERSONAL, "Pre-condition"
    a1 = m1.account

    update_account_type(a1, new_account_type=AccountType.PERSONAL)

    a1.refresh_from_db()
    assert a1.account_type == AccountType.PERSONAL

    update_account_type(a1, new_account_type=AccountType.TEAM)

    a1.refresh_from_db()
    assert a1.account_type == AccountType.TEAM


@pytest.mark.django_db
def test_delete_account():
    initial_account_count = Account.objects.count()
    initial_membership_count = Membership.objects.count()

    u1 = UserFactory.create(
        account__account_type=AccountType.TEAM, membership__role=Role.OWNER
    )
    m1 = Membership.objects.get(user=u1)
    assert m1.user == u1, "Pre-condition"
    assert m1.role == Role.OWNER, "Pre-condition"
    assert m1.account.account_type == AccountType.TEAM, "Pre-condition"
    a1 = m1.account

    u2 = UserFactory.create(
        account__account_type=AccountType.PERSONAL, membership__role=Role.OWNER
    )
    m2 = Membership.objects.get(user=u2)
    assert m2.user == u2, "Pre-condition"
    assert m2.role == Role.OWNER, "Pre-condition"
    assert m2.account.account_type == AccountType.PERSONAL, "Pre-condition"
    a2 = m2.account

    a3 = create_team_account(name="Team Account 3")
    a4 = create_team_account(name="Team Account 4")
    m31 = create_membership(account=a3, user=u1, role=Role.OWNER)  # noqa: F841
    m41 = create_membership(account=a4, user=u1, role=Role.OWNER)  # noqa: F841
    m42 = create_membership(account=a4, user=u2, role=Role.MEMBER)  # noqa: F841

    a5 = create_personal_account(name="Personal Account 5")
    a6 = create_team_account(name="Team Account 6")

    assert delete_account(a1) == (2, {"accounts.Account": 1, "accounts.Membership": 1})
    assert delete_account(a2) == (2, {"accounts.Account": 1, "accounts.Membership": 1})
    assert delete_account(a3) == (2, {"accounts.Account": 1, "accounts.Membership": 1})
    assert delete_account(a4) == (3, {"accounts.Account": 1, "accounts.Membership": 2})
    assert delete_account(a5) == (1, {"accounts.Account": 1})
    assert delete_account(a6) == (1, {"accounts.Account": 1})

    assert Account.objects.count() == initial_account_count
    assert Membership.objects.count() == initial_membership_count


@contextmanager
def _patch_account_profile_image_delete_logger() -> Generator[MagicMock]:
    """
    Patches the `logger.exception` call inside `Account._try_and_delete_profile_image`.

    Both the happy-path tests (`assert_not_called`) and the negative/crash tests
    (`assert_called_once`) use this same helper so the patch target is defined in
    one place. If the implementation moves the logger, fixing this helper fixes
    every test that depends on it.
    """
    with patch("backend.accounts.models.accounts.logger.exception") as mock_log_exc:
        yield mock_log_exc


@pytest.mark.django_db
@pytest.mark.parametrize("account_type", [*AccountType])
def test_update_and_delete_uploaded_profile_image_success_paths(
    account_type: AccountType,
):
    def make_test_image(filename: str, *, r: int, g: int, b: int):
        image_file = create_test_image(filename, r=r, g=g, b=b)
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

    uploaded_image1 = make_test_image("accounts-test-image1.png", r=127, g=128, b=129)

    a1 = create_account(account_type=account_type, name="Account for Image Test")
    assert not a1.uploaded_profile_image, "Pre-condition"

    result1 = update_uploaded_profile_image(a1, uploaded_image1)

    assert isinstance(result1, AccountUpdateUploadedProfileImageSuccessResult)
    assert result1.account == a1
    assert result1.uploaded_profile_image == uploaded_image1

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image1.seek(0)
    # Make sure the uploaded image exactly matches.
    assert a1.uploaded_profile_image.read() == uploaded_image1.read()
    i1_name = a1.uploaded_profile_image.name
    i1_url = a1.uploaded_profile_image.url
    i1_path = a1.uploaded_profile_image.path
    assert i1_name and "accounts-test-image1.png" in i1_name
    assert i1_url and "accounts-test-image1.png" in i1_url
    assert i1_path and "accounts-test-image1.png" in i1_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    # Make sure it exists in the storage where we expect it to be.
    assert storage.exists(i1_name), "Pre-condition"

    uploaded_image1.close()
    a1.uploaded_profile_image.close()

    # NOTE: These must be different than `uploaded_image1`'s at the byte level.
    uploaded_image2 = make_test_image("accounts-test-image2.png", r=151, g=152, b=153)
    # Make this the same bytes structure as `uploaded_image2`.
    uploaded_image31 = make_test_image("accounts-test-image3.png", r=151, g=152, b=153)
    # This should be the exact same filename and bytes structure as `uploaded_image31`.
    uploaded_image32 = make_test_image("accounts-test-image3.png", r=151, g=152, b=153)
    # This should be the same filename but a different bytes structure.
    uploaded_image33 = make_test_image("accounts-test-image3.png", r=153, g=154, b=155)

    # Replacing an image triggers the `FieldTracker` path in `save()`. Verify that the
    # `LightStateFieldFile` cleanup does not hit the exception handler.
    with _patch_account_profile_image_delete_logger() as mock_log_exc:
        result2 = update_uploaded_profile_image(a1, uploaded_image2)
        mock_log_exc.assert_not_called()
    assert isinstance(result2, AccountUpdateUploadedProfileImageSuccessResult)
    assert result2.account == a1
    assert result2.uploaded_profile_image == uploaded_image2

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image2.seek(0)
    # Make sure the uploaded image exactly matches.
    assert a1.uploaded_profile_image.read() == uploaded_image2.read()
    i2_name = a1.uploaded_profile_image.name
    i2_url = a1.uploaded_profile_image.url
    i2_path = a1.uploaded_profile_image.path
    assert i2_name and "accounts-test-image2.png" in i2_name
    assert i2_url and "accounts-test-image2.png" in i2_url
    assert i2_path and "accounts-test-image2.png" in i2_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    # Make sure it exists in the storage where we expect it to be.
    assert storage.exists(i2_name), "Pre-condition"

    # Make sure the old image was removed.
    assert not storage.exists(i1_name), "Pre-condition"

    uploaded_image2.close()
    a1.uploaded_profile_image.close()

    result31 = update_uploaded_profile_image(a1, uploaded_image31)
    assert isinstance(result31, AccountUpdateUploadedProfileImageSuccessResult)
    assert result31.account == a1
    assert result31.uploaded_profile_image == uploaded_image31

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image31.seek(0)
    assert a1.uploaded_profile_image.read() == uploaded_image31.read()
    i31_name = a1.uploaded_profile_image.name
    i31_url = a1.uploaded_profile_image.url
    i31_path = a1.uploaded_profile_image.path
    assert i31_name and "accounts-test-image3.png" in i31_name
    assert i31_url and "accounts-test-image3.png" in i31_url
    assert i31_path and "accounts-test-image3.png" in i31_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    # Make sure it exists in the storage where we expect it to be.
    assert storage.exists(i31_name), "Pre-condition"

    assert not storage.exists(i1_name), "Pre-condition"
    assert not storage.exists(i2_name), "Pre-condition"

    uploaded_image31.close()
    a1.uploaded_profile_image.close()

    result32 = update_uploaded_profile_image(a1, uploaded_image32)
    assert isinstance(result32, AccountUpdateUploadedProfileImageSuccessResult)
    assert result32.account == a1
    assert result32.uploaded_profile_image == uploaded_image32

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image32.seek(0)
    assert a1.uploaded_profile_image.read() == uploaded_image32.read()
    i32_name = a1.uploaded_profile_image.name
    i32_url = a1.uploaded_profile_image.url
    i32_path = a1.uploaded_profile_image.path
    assert i32_name and "accounts-test-image3.png" in i32_name
    assert i32_url and "accounts-test-image3.png" in i32_url
    assert i32_path and "accounts-test-image3.png" in i32_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    # Make sure it exists in the storage where we expect it to be.
    assert storage.exists(i32_name), "Pre-condition"

    assert not storage.exists(i1_name), "Pre-condition"
    assert not storage.exists(i2_name), "Pre-condition"
    assert not storage.exists(i31_name), "Pre-condition"

    uploaded_image32.close()
    a1.uploaded_profile_image.close()

    result33 = update_uploaded_profile_image(a1, uploaded_image33)
    assert isinstance(result33, AccountUpdateUploadedProfileImageSuccessResult)
    assert result33.account == a1
    assert result33.uploaded_profile_image == uploaded_image33

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image33.seek(0)
    assert a1.uploaded_profile_image.read() == uploaded_image33.read()
    i33_name = a1.uploaded_profile_image.name
    i33_url = a1.uploaded_profile_image.url
    i33_path = a1.uploaded_profile_image.path
    assert i33_name and "accounts-test-image3.png" in i33_name
    assert i33_url and "accounts-test-image3.png" in i33_url
    assert i33_path and "accounts-test-image3.png" in i33_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    # Make sure it exists in the storage where we expect it to be.
    assert storage.exists(i33_name), "Pre-condition"

    assert not storage.exists(i1_name), "Pre-condition"
    assert not storage.exists(i2_name), "Pre-condition"
    assert not storage.exists(i31_name), "Pre-condition"
    assert not storage.exists(i32_name), "Pre-condition"

    uploaded_image33.close()
    a1.uploaded_profile_image.close()

    # The file names should have various random prefixes applied which makes these not
    # equal.
    #
    # NOTE: These should not, in practice, ever equal each other. However, if they do on
    # very very rare occasions and break, say, CI sometimes, then running
    # https://github.com/pytest-dev/pytest-rerunfailures with say 4-7 retries should
    # hopefully be sufficient to work around that. Alternatively (probably a better
    # solution), you could patch `sanitize_filename_for_storage` to append a number to
    # the beginning or end somewhere that's always auto-incrementing, etc.
    assert i31_name != i32_name
    assert i31_name != i33_name
    assert i31_url != i32_url
    assert i31_url != i33_url
    assert i31_path != i32_path
    assert i31_path != i33_path

    # Deleting via the op triggers the same `FieldTracker`/`LightStateFieldFile` path.
    with _patch_account_profile_image_delete_logger() as mock_log_exc:
        delete_uploaded_profile_image(a1)
        mock_log_exc.assert_not_called()
    a1.refresh_from_db()

    assert not a1.uploaded_profile_image

    assert not storage.exists(i33_name)
    assert not storage.exists(i32_name)
    assert not storage.exists(i31_name)
    assert not storage.exists(i2_name)
    assert not storage.exists(i1_name)

    uploaded_image4 = make_test_image("accounts-test-image4.png", r=175, g=176, b=177)
    result4 = update_uploaded_profile_image(a1, uploaded_image4)
    assert isinstance(result4, AccountUpdateUploadedProfileImageSuccessResult)
    assert result4.account == a1
    assert result4.uploaded_profile_image == uploaded_image4

    a1.refresh_from_db()
    assert a1.uploaded_profile_image
    uploaded_image4.seek(0)
    assert a1.uploaded_profile_image.read() == uploaded_image4.read()
    i4_name = a1.uploaded_profile_image.name
    i4_url = a1.uploaded_profile_image.url
    i4_path = a1.uploaded_profile_image.path
    assert i4_name and "accounts-test-image4.png" in i4_name
    assert i4_url and "accounts-test-image4.png" in i4_url
    assert i4_path and "accounts-test-image4.png" in i4_path
    storage = a1._meta.get_field("uploaded_profile_image").storage
    assert storage.exists(i4_name), "Pre-condition"

    # Finally, delete the account and make sure the image is deleted.
    a1.delete()
    with pytest.raises(Account.DoesNotExist):
        a1.refresh_from_db()
    assert not storage.exists(i4_name)


@pytest.mark.django_db
@pytest.mark.parametrize("account_type", [*AccountType])
def test_update_uploaded_profile_image_failure_paths(account_type: AccountType):
    def make_test_image(
        filename: str,
        *,
        r: int,
        g: int,
        b: int,
        size_x: int,
        size_y: int,
    ):
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

    a1 = create_account(account_type=account_type, name="Account for Image Test")

    uploaded_image_missing_image = make_test_image(
        "accounts-test-image1.png", r=127, g=128, b=129, size_x=128, size_y=128
    )
    del uploaded_image_missing_image.image
    uploaded_image_too_large = make_test_image(
        "accounts-test-image1.png", r=128, g=129, b=130, size_x=1_025, size_y=1_025
    )

    uploaded_image_size_too_big = make_test_image(
        "accounts-test-image1.png", r=128, g=129, b=130, size_x=128, size_y=128
    )
    uploaded_image_size_too_big.size = 3_000_001  # 3MB + 1 byte (SI units)

    uploaded_image_valid1 = make_test_image(
        "accounts-test-image1.png", r=129, g=130, b=131, size_x=1_024, size_y=1_024
    )
    uploaded_image_valid2 = make_test_image(
        "accounts-test-image2.png", r=130, g=131, b=132, size_x=1_024, size_y=1_024
    )
    uploaded_image_valid2.size = 3_000_000  # Exactly 3MB (SI units)

    result_missing = update_uploaded_profile_image(a1, uploaded_image_missing_image)
    assert isinstance(result_missing, AccountUpdateUploadedProfileImageFailedResult)
    assert result_missing.account == a1
    assert result_missing.uploaded_profile_image == uploaded_image_missing_image
    assert result_missing.message == (
        "The image uploaded cannot be accepted. Please make sure you uploaded a "
        "valid image file. Also, note that we only accept images that are no "
        "larger than 1024 X 1024."
    )
    assert result_missing.code == "invalid"

    result_too_large = update_uploaded_profile_image(a1, uploaded_image_too_large)
    assert isinstance(result_too_large, AccountUpdateUploadedProfileImageFailedResult)
    assert result_too_large.account == a1
    assert result_too_large.uploaded_profile_image == uploaded_image_too_large
    assert (
        result_too_large.message
        == "This image exceeds 1024 X 1024. Please reduce its size and try again."
    )
    assert result_too_large.code == "invalid_dimensions"

    result_size_too_big = update_uploaded_profile_image(a1, uploaded_image_size_too_big)
    assert isinstance(
        result_size_too_big, AccountUpdateUploadedProfileImageFailedResult
    )
    assert result_size_too_big.account == a1
    assert result_size_too_big.uploaded_profile_image == uploaded_image_size_too_big
    assert result_size_too_big.message == "The file size can be at most 3.0 MB."
    assert result_size_too_big.code == "invalid_file_size"

    result_valid1 = update_uploaded_profile_image(a1, uploaded_image_valid1)
    assert isinstance(result_valid1, AccountUpdateUploadedProfileImageSuccessResult)
    assert result_valid1.account == a1
    assert result_valid1.uploaded_profile_image == uploaded_image_valid1

    result_valid2 = update_uploaded_profile_image(a1, uploaded_image_valid2)
    assert isinstance(result_valid2, AccountUpdateUploadedProfileImageSuccessResult)
    assert result_valid2.account == a1
    assert result_valid2.uploaded_profile_image == uploaded_image_valid2


@pytest.mark.django_db
@pytest.mark.parametrize("account_type", [*AccountType])
def test_account_profile_image_storage_failure_logs_exception(
    account_type: AccountType,
):
    """
    Intentionally breaks storage deletion to verify that `logger.exception` is
    actually called with the expected message and kwargs. This confirms that the
    `assert_not_called` checks in the happy-path tests are patching the correct
    target — if the patch target were wrong, this test would fail because the mock
    would never be called.
    """

    def make_test_image(filename: str, *, r: int, g: int, b: int):
        image_file = create_test_image(filename, r=r, g=g, b=b)
        image_file.seek(0)
        simple_uploaded_file = SimpleUploadedFile(
            name=image_file.name,  # type: ignore[arg-type]
            content=image_file.read(),
            content_type="image/png",
        )
        image_file.seek(0)
        simple_uploaded_file.seek(0)
        return DjangoFormsImageField().clean(simple_uploaded_file)

    a1 = create_account(account_type=account_type, name="Account for Crash Test")
    storage = a1._meta.get_field("uploaded_profile_image").storage

    # Upload an initial image so there's something for the tracker to detect.
    img1 = make_test_image("acct-crash-1.png", r=200, g=0, b=0)
    update_uploaded_profile_image(a1, img1)
    a1.refresh_from_db()
    assert a1.uploaded_profile_image, "Pre-condition"

    # Replace with a second image, but sabotage `storage.delete` so the cleanup
    # of the old image fails.
    img2 = make_test_image("acct-crash-2.png", r=0, g=200, b=0)
    with (
        patch.object(
            storage, "delete", side_effect=OSError("Simulated storage failure")
        ),
        _patch_account_profile_image_delete_logger() as mock_log_exc,
    ):
        result = update_uploaded_profile_image(a1, img2)
        assert isinstance(result, AccountUpdateUploadedProfileImageSuccessResult)

        mock_log_exc.assert_called_once()
        log_message = mock_log_exc.call_args[0][0]
        log_kwargs = mock_log_exc.call_args[1]

        assert "Account" in log_message
        assert "profile image" in log_message
        assert log_kwargs["account_pk"] == a1.pk
        assert log_kwargs["account_name"] == a1.name
        assert log_kwargs["did_just_delete_account"] is False
