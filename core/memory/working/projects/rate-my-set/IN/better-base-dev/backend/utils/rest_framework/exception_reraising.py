from __future__ import annotations

from functools import wraps

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ErrorDetail, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError


def reraise_as_permission_denied(*, codes_set: set[str] | frozenset[str]):
    """
    Define a decorator that will pass through unless a `DjangoValidationError` (Django
    built in `ValidationError`) or `DRFValidationError` (DRF `ValidationError`) is
    raised. If one of those is raised, it will check if one of the `codes_set` is
    present, and, if so, re-raise the exception as a `PermissionDenied` exception.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (DjangoValidationError, DRFValidationError) as e:
                try:
                    if isinstance(e, DRFValidationError):
                        if (
                            isinstance(e.detail, list)
                            and isinstance(e.detail[0], ErrorDetail)
                            and (set(e.get_codes()) & codes_set)  # type: ignore[arg-type]
                        ):
                            raise PermissionDenied(e.detail[0]) from e
                    else:
                        assert isinstance(e, DjangoValidationError), "Pre-condition"
                        if (
                            hasattr(e, "code")
                            and e.code
                            and ({e.code} & codes_set)
                            and e.message
                        ):
                            raise PermissionDenied(e.message, e.code) from e
                except Exception as raised_e:
                    if isinstance(raised_e, PermissionDenied):
                        raise
                    # If checking for the codes above caused a non-`PermissionDenied`
                    # exception to be thrown, then we'll re-throw the original
                    # exception. There are a lot of different possible structures for
                    # `DRFValidationError` and `DjangoValidationError`s, so it's
                    # possible that the above code could fail/crash in some edge cases,
                    # etc.
                    raise e  # noqa: B904
                raise

        return wrapper

    return decorator
