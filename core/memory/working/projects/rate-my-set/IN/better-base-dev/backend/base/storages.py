from __future__ import annotations

from django.conf import settings
from django.core.files.storage import Storage

from backend.base.ops.environment import get_environment

_environment = get_environment()

DefaultMediaStorage: type[Storage]
DefaultPublicMediaStorage: type[Storage]
DefaultPrivateMediaStorage: type[Storage]

# Setup for file system storage for production (and also staging).
if _environment.is_prod or _environment.is_stage:
    from storages.backends.s3 import S3Storage

    class MediaS3PublicStorage(S3Storage):
        bucket_name = (
            settings.AWS_PUBLIC_STORAGE_BUCKET_NAME or settings.AWS_STORAGE_BUCKET_NAME  # type: ignore[misc]
        )
        custom_domain = (
            settings.AWS_S3_PUBLIC_CUSTOM_DOMAIN or settings.AWS_S3_CUSTOM_DOMAIN  # type: ignore[misc]
        )
        default_acl = "public-read"
        endpoint_url = (
            settings.AWS_S3_PUBLIC_ENDPOINT_URL or settings.AWS_S3_ENDPOINT_URL  # type: ignore[misc]
        )
        file_overwrite = False
        location = "media"
        querystring_auth = False

    class MediaS3PrivateStorage(S3Storage):
        bucket_name = (
            settings.AWS_PRIVATE_STORAGE_BUCKET_NAME or settings.AWS_STORAGE_BUCKET_NAME  # type: ignore[misc]
        )
        # NOTE: Set `custom_domain = None` and commented out the below because for R2,
        # `endpoint_url` is all we need. If we have a non-`None` custom domain then we
        # won't get a signed URL with R2 which is not what we want.
        custom_domain = None
        # custom_domain = (
        #     settings.AWS_S3_PRIVATE_CUSTOM_DOMAIN or settings.AWS_S3_CUSTOM_DOMAIN  # type: ignore[misc]
        # )
        default_acl = "private"
        endpoint_url = (
            settings.AWS_S3_PRIVATE_ENDPOINT_URL or settings.AWS_S3_ENDPOINT_URL  # type: ignore[misc]
        )
        file_overwrite = False
        location = "media"
        querystring_auth = True

    MediaS3Storage = MediaS3PrivateStorage

    DefaultMediaStorage = MediaS3Storage
    DefaultPublicMediaStorage = MediaS3PublicStorage
    DefaultPrivateMediaStorage = MediaS3PrivateStorage

# Setup for in memory file storage for tests.
elif _environment.is_test or _environment.is_ci or _environment.is_running_tests:
    assert not _environment.is_prod, "Pre-condition"

    from django.core.files.storage.memory import InMemoryStorage

    class PublicInMemoryStorage(InMemoryStorage):
        def __init__(
            self,
            location=f"{settings.MEDIA_ROOT}/public",
            base_url=f"{settings.MEDIA_URL}public",
            **kwargs,
        ):
            super().__init__(location=location, base_url=base_url, **kwargs)

    class PrivateInMemoryStorage(InMemoryStorage):
        def __init__(
            self,
            location=f"{settings.MEDIA_ROOT}/private",
            base_url=f"{settings.MEDIA_URL}private",
            **kwargs,
        ):
            super().__init__(location=location, base_url=base_url, **kwargs)

    DefaultMediaStorage = PrivateInMemoryStorage
    DefaultPublicMediaStorage = PublicInMemoryStorage
    DefaultPrivateMediaStorage = PrivateInMemoryStorage

# Setup for file system storage for development.
else:
    assert not _environment.is_prod, "Pre-condition"

    from django.core.files.storage import FileSystemStorage

    class PublicFileSystemStorage(FileSystemStorage):
        def __init__(
            self,
            location=f"{settings.MEDIA_ROOT}/public",
            base_url=f"{settings.MEDIA_URL}public",
            **kwargs,
        ):
            kwargs.setdefault("allow_overwrite", False)

            super().__init__(location=location, base_url=base_url, **kwargs)

    class PrivateFileSystemStorage(FileSystemStorage):
        def __init__(
            self,
            location=f"{settings.MEDIA_ROOT}/private",
            base_url=f"{settings.MEDIA_URL}private",
            **kwargs,
        ):
            super().__init__(location=location, base_url=base_url, **kwargs)

    DefaultMediaStorage = PrivateFileSystemStorage
    DefaultPublicMediaStorage = PublicFileSystemStorage
    DefaultPrivateMediaStorage = PrivateFileSystemStorage


_default_media_storage: Storage | None = None
_default_public_media_storage: Storage | None = None
_default_private_media_storage: Storage | None = None


def get_default_media_storage() -> Storage:
    global _default_media_storage

    if _default_media_storage is None:
        _default_media_storage = DefaultMediaStorage()

    return _default_media_storage


def get_default_public_media_storage() -> Storage:
    global _default_public_media_storage

    if _default_public_media_storage is None:
        _default_public_media_storage = DefaultPublicMediaStorage()

    return _default_public_media_storage


def get_default_private_media_storage() -> Storage:
    global _default_private_media_storage

    if _default_private_media_storage is None:
        _default_private_media_storage = DefaultPrivateMediaStorage()

    return _default_private_media_storage
