from __future__ import annotations

from dataclasses import dataclass
from typing import overload

import structlog
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise
from humanize.filesize import naturalsize
from PIL import ImageFile

from backend.accounts.models import Account, User
from backend.utils.transactions import (
    is_in_transaction,
)

logger = structlog.stdlib.get_logger()


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountUpdateUploadedProfileImageSuccessResult:
    account: Account
    uploaded_profile_image: InMemoryUploadedFile


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountUpdateUploadedProfileImageFailedResult:
    account: Account
    uploaded_profile_image: InMemoryUploadedFile
    message: StrOrPromise
    code: str


@dataclass(frozen=True, kw_only=True, slots=True)
class UserUpdateUploadedProfileImageSuccessResult:
    user: User
    uploaded_profile_image: InMemoryUploadedFile


@dataclass(frozen=True, kw_only=True, slots=True)
class UserUpdateUploadedProfileImageFailedResult:
    user: User
    uploaded_profile_image: InMemoryUploadedFile
    message: StrOrPromise
    code: str


@overload
def update_uploaded_profile_image_op(  # type: ignore[overload-overlap,unused-ignore]
    account_or_user: Account, uploaded_profile_image: InMemoryUploadedFile
) -> (
    AccountUpdateUploadedProfileImageSuccessResult
    | AccountUpdateUploadedProfileImageFailedResult
): ...


@overload
def update_uploaded_profile_image_op(
    account_or_user: User, uploaded_profile_image: InMemoryUploadedFile
) -> (
    UserUpdateUploadedProfileImageSuccessResult
    | UserUpdateUploadedProfileImageFailedResult
): ...


def update_uploaded_profile_image_op(
    account_or_user: Account | User, uploaded_profile_image: InMemoryUploadedFile
) -> (
    AccountUpdateUploadedProfileImageSuccessResult
    | AccountUpdateUploadedProfileImageFailedResult
    | UserUpdateUploadedProfileImageSuccessResult
    | UserUpdateUploadedProfileImageFailedResult
):
    assert is_in_transaction(), "Pre-condition"

    max_width: int = 1024
    max_height: int = 1024

    default_message = _(
        "The image uploaded cannot be accepted. Please make sure you uploaded a valid "
        "image file. Also, note that we only accept images that are no larger than "
        "%(max_width)s X %(max_height)s."
    ) % {"max_width": max_width, "max_height": max_height}
    default_code = "invalid"

    def construct_failed_result(
        message: StrOrPromise = default_message, code: str = default_code
    ) -> (
        AccountUpdateUploadedProfileImageFailedResult
        | UserUpdateUploadedProfileImageFailedResult
    ):
        if isinstance(account_or_user, Account):
            return AccountUpdateUploadedProfileImageFailedResult(
                account=account_or_user,
                uploaded_profile_image=uploaded_profile_image,
                message=message,
                code=code,
            )
        else:
            return UserUpdateUploadedProfileImageFailedResult(
                user=account_or_user,
                uploaded_profile_image=uploaded_profile_image,
                message=message,
                code=code,
            )

    file_name: str = uploaded_profile_image.name  # type: ignore[assignment]
    file_size: int = uploaded_profile_image.size  # type: ignore[assignment]
    assert file_name and isinstance(file_name, str), "Current pre-condition"
    assert file_size is not None and file_size >= 0, "Current pre-condition"

    try:
        image: ImageFile.ImageFile = uploaded_profile_image.image  # type: ignore[attr-defined]

        image_width = image.width
        image_height = image.height
    except Exception:
        logger.exception("Failed to get `image` from `uploaded_profile_image`.")
        return construct_failed_result()
    else:
        # Check that the file dimensions are within the valid limits.
        invalid_dimensions_message = _(
            "This image exceeds %(max_width)s X %(max_height)s. "
            "Please reduce its size and try again."
        ) % {
            "max_width": max_width,
            "max_height": max_height,
        }
        invalid_dimensions_code = "invalid_dimensions"
        if image_width is None or image_width <= 0 or image_width > max_width:
            return construct_failed_result(
                invalid_dimensions_message, invalid_dimensions_code
            )
        if image_height is None or image_height <= 0 or image_height > max_height:
            return construct_failed_result(
                invalid_dimensions_message, invalid_dimensions_code
            )

    # Check that the file size is not too large.
    max_size = 3_000_000  # 3MB (using SI units for display)
    if file_size > max_size:
        return construct_failed_result(
            (
                _("The file size can be at most %(max_file_size)s.")
                % {
                    "max_file_size": naturalsize(max_size),
                }
            ),
            "invalid_file_size",
        )

    account_or_user.uploaded_profile_image.save(
        file_name, uploaded_profile_image, save=False
    )
    account_or_user.save(update_fields=["uploaded_profile_image", "modified"])

    if isinstance(account_or_user, Account):
        return AccountUpdateUploadedProfileImageSuccessResult(
            account=account_or_user,
            uploaded_profile_image=uploaded_profile_image,
        )

    return UserUpdateUploadedProfileImageSuccessResult(
        user=account_or_user,
        uploaded_profile_image=uploaded_profile_image,
    )
