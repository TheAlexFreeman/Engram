from __future__ import annotations

from datetime import datetime
from typing import Final

from django.http import HttpRequest
from django.utils import timezone

from backend.accounts.models.memberships import Membership
from backend.accounts.models.users import User
from backend.accounts.models.users_app_states import UserAppState

CURRENT_MEMBERSHIP_ID_SESSION_KEY: Final[str] = "current_membership_id"


def get_user_app_state(user: User) -> UserAppState:
    try:
        return user.app_state
    except UserAppState.DoesNotExist:
        return UserAppState.objects.get_or_create(user=user)[0]


def get_current_membership_id_from_best_source(
    *,
    user: User,
    request: HttpRequest | None,
) -> int | None:
    if (
        request is not None
        and (session_value := get_current_membership_id_from_session(request=request))
        is not None
    ):
        return session_value

    app_state = get_user_app_state(user)
    return get_current_membership_id_from_app_state(app_state)


def get_current_membership_id_from_session(*, request: HttpRequest) -> int | None:
    try:
        str_value = request.session.get(CURRENT_MEMBERSHIP_ID_SESSION_KEY, None)
        int_value = int(str_value)
        return int_value
    except TypeError, ValueError, OverflowError:
        return None


def get_current_membership_id_from_app_state(app_state: UserAppState) -> int | None:
    return app_state.current_membership_id


def set_current_membership_in_all_places(
    user: User,
    membership: Membership,
    *,
    request: HttpRequest,
    allow_unauthenticated_session: bool = False,
) -> None:
    set_current_membership_in_session(
        user=user,
        membership=membership,
        request=request,
        allow_unauthenticated_session=allow_unauthenticated_session,
    )
    now = timezone.now()
    set_current_membership_in_app_state(user=user, membership=membership, now=now)
    set_current_membership_in_membership_model(membership=membership, now=now)


def set_current_membership_in_session(
    user: User,
    membership: Membership,
    *,
    request: HttpRequest,
    allow_unauthenticated_session: bool = False,
) -> None:
    assert user is not None and user.is_authenticated and user.pk is not None, (
        "Pre-condition"
    )
    assert membership.user_id == user.pk, "Pre-condition"
    if allow_unauthenticated_session and not request.user.is_authenticated:
        pass
    else:
        assert request.user == user, "Current pre-condition/check"

    request.session[CURRENT_MEMBERSHIP_ID_SESSION_KEY] = str(membership.pk)


def set_current_membership_in_app_state(
    user: User,
    membership: Membership,
    *,
    now: datetime | None = None,
) -> None:
    assert user is not None and user.is_authenticated and user.pk is not None, (
        "Pre-condition"
    )
    assert membership.user_id == user.pk, "Pre-condition"

    app_state = get_user_app_state(user)

    app_state.current_membership_id = membership.pk
    app_state.current_membership_id_as_of = now or timezone.now()
    app_state.save(
        update_fields=[
            "current_membership_id",
            "current_membership_id_as_of",
            "modified",
        ]
    )


def set_current_membership_in_membership_model(
    membership: Membership,
    *,
    now: datetime | None = None,
) -> None:
    now_to_use = now or timezone.now()
    # Skip updating `modified` or anything like that, just update this one field in the
    # DB with little overhead.
    membership.__class__.objects.filter(pk=membership.pk).update(
        last_selected_at=now_to_use
    )
    # Set the same value on the instance in memory so that it's up to date.
    membership.last_selected_at = now_to_use
