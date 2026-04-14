from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, NotRequired, TypedDict, Unpack

from django.http import HttpRequest


class PotentialFrontendExtraSignalingData(TypedDict):
    immediately_redirect_to: NotRequired[str]


FRONTEND_EXTRA_SIGNALING_REQUEST_ATTRIBUTE: Final[str] = "_frontend_extra_signaling_"
FRONTEND_EXTRA_DATA_BRING_IN_REQUEST_ATTRIBUTE: Final[str] = (
    "_frontend_extra_data_bring_in_"
)


def get_frontend_extra_signaling_data(
    request: HttpRequest,
) -> PotentialFrontendExtraSignalingData:
    return getattr(request, FRONTEND_EXTRA_SIGNALING_REQUEST_ATTRIBUTE, {}) or {}  # type: ignore[return-value]


def set_frontend_extra_signaling_data(
    request: HttpRequest,
    *,
    merger: Callable[
        [PotentialFrontendExtraSignalingData], PotentialFrontendExtraSignalingData
    ]
    | None = None,
    **data: Unpack[PotentialFrontendExtraSignalingData],
) -> PotentialFrontendExtraSignalingData:
    attr_str = FRONTEND_EXTRA_SIGNALING_REQUEST_ATTRIBUTE

    if not hasattr(request, attr_str):
        setattr(request, attr_str, {})

    value = getattr(request, attr_str)

    if data:
        value = value | data
        setattr(request, attr_str, value)

    if merger is not None:
        value = merger(value)
        setattr(request, attr_str, value)

    return value


def get_frontend_extra_data_to_bring_in(
    request: HttpRequest,
) -> dict[str, Any]:
    return getattr(request, FRONTEND_EXTRA_DATA_BRING_IN_REQUEST_ATTRIBUTE, {}) or {}


def set_frontend_extra_data_to_bring_in(
    request: HttpRequest,
    *,
    merger: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    **data: Unpack[dict[str, Any]],  # type: ignore[misc]
) -> dict[str, Any]:
    attr_str = FRONTEND_EXTRA_DATA_BRING_IN_REQUEST_ATTRIBUTE

    if not hasattr(request, attr_str):
        setattr(request, attr_str, {})

    value = getattr(request, attr_str)

    if data:
        value = value | data
        setattr(request, attr_str, value)

    if merger is not None:
        value = merger(value)
        setattr(request, attr_str, value)

    return value
