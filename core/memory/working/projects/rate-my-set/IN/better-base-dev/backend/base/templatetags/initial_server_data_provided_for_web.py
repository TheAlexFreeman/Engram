from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, TypedDict, cast

import structlog
from django import template
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.http import HttpRequest
from django.template import RequestContext, Template
from django.template.loader import get_template
from djangorestframework_camel_case.util import camelize

from backend.accounts.api.serializers.memberships import (
    MembershipReadOnlyUserNotIncludedSerializer,
)
from backend.accounts.api.serializers.users import (
    AnonymousUserReadOnlySerializer,
    UserReadOnlySerializer,
)
from backend.accounts.models import Membership, User
from backend.accounts.ops.users_app_states import (
    get_current_membership_id_from_best_source,
)
from backend.base.ops.frontend_extra_signaling import (
    get_frontend_extra_data_to_bring_in,
    get_frontend_extra_signaling_data,
)

logger = structlog.stdlib.get_logger()

register = template.Library()


# https://docs.djangoproject.com/en/4.2/howto/custom-template-tags/#inclusion-tags
@register.inclusion_tag(
    cast(Template, get_template("base/initial_server_data_provided_for_web.html")),
    takes_context=True,
)
def initial_server_data_provided_for_web(context: RequestContext):
    request: HttpRequest = context["request"]

    all_data = get_all_data(context=context, request=request, camel_case=True)

    return {"all_data": all_data}


def get_all_data(
    *, context: RequestContext, request: HttpRequest, camel_case: bool = False
):
    user: User | AnonymousUser = request.user

    messages_data = get_and_clear_messages_data(request=request)
    csrf_token = get_csrf_token(context=context)
    user_data = get_user_data(user=user)
    memberships_data = get_memberships_data(user=user)
    session_data = get_session_data(request=request)
    current_membership_data = get_current_membership_data(
        user=user,
        memberships_data=memberships_data,
        request=request,
    )

    check_and_potentially_load_followed_invitation_data(request=request)

    extra_data = get_extra_data(request=request)

    all_data = {
        "messages": messages_data,
        "csrf_token": csrf_token,
        "user": user_data,
        "memberships": memberships_data,
        "session": session_data,
        "current_membership": current_membership_data,
        "extra": extra_data,
    }

    if camel_case:
        all_data = camelize(all_data)

    return all_data


class MessageDict(TypedDict):
    message: str
    level: int
    tags: str
    extra_tags: str
    level_tag: str


def get_and_clear_messages_data(*, request: HttpRequest) -> list[MessageDict]:
    storage = get_messages(request)
    message_dicts: list[MessageDict] = []
    for message in storage:
        message_dicts.append(
            {
                "message": message.message,
                "level": message.level,
                "tags": message.tags,
                "extra_tags": message.extra_tags,
                "level_tag": message.level_tag,
            }
        )
    return message_dicts


def get_csrf_token(*, context: RequestContext) -> str | None:
    start_with = "<<<start>>>"
    end_with = "<<<end>>>"
    template_string = f"{start_with}{{% csrf_token %}}{end_with}"
    template_object = Template(template_string)
    rendered = template_object.render(context)
    after_start = rendered.split(start_with)[1]
    before_end = after_start.split(end_with)[0]
    csrf_regex = r"value=\"([^\"]+)\""
    if match := re.search(csrf_regex, before_end):
        return match.group(1) or None
    return before_end or None


def get_user_data(*, user: User | AnonymousUser) -> dict[str, Any]:
    if isinstance(user, User):
        return UserReadOnlySerializer(user).data
    return AnonymousUserReadOnlySerializer(user).data


def get_memberships_data(*, user: User | AnonymousUser) -> list[dict[str, Any]]:
    if not isinstance(user, User):
        return []
    memberships = (
        Membership.objects.filter(user=user)
        .with_significant_relations_select_related()
        .with_role_priority()
        .with_user_last_selected_at_ordering()
    )
    return MembershipReadOnlyUserNotIncludedSerializer(memberships, many=True).data  # type: ignore[return-value]


def get_session_data(*, request: HttpRequest) -> dict[str, Any]:
    is_authenticated = request.user.is_authenticated

    return {
        "is_authenticated": is_authenticated,
    }


def get_current_membership_data(
    *,
    user: User | AnonymousUser,
    memberships_data: list[dict[str, Any]],
    request: HttpRequest,
) -> dict[str, Any] | None:
    if not isinstance(user, User):
        return None
    stored_membership_id = get_current_membership_id_from_best_source(
        user=user, request=request
    )
    for m in memberships_data:
        m_id = m.get("id")
        if (
            m_id is not None
            and stored_membership_id is not None
            and m_id == stored_membership_id
        ):
            return m
    if memberships_data:
        return memberships_data[0]
    return None


def get_extra_data(*, request: HttpRequest) -> dict[str, Any]:
    signaling_data = get_frontend_extra_signaling_data(request)
    extra_data_to_bring_in = get_frontend_extra_data_to_bring_in(request)
    return {"signaling": signaling_data, **extra_data_to_bring_in}


def check_and_potentially_load_followed_invitation_data(
    *, request: HttpRequest
) -> bool:
    path = request.path or ""

    if ("/follow-invitation" in path) or (
        "/from-invitation" in path and ("signup" in path or "login" in path)
    ):
        invitation_ops = _get_invitation_ops()
        invitation_ops.check_and_load_followed_invitation_data(
            request=request, set_immediately_redirect_to=False
        )
        return True

    return False


@lru_cache(maxsize=1)
def _get_invitation_ops():
    from backend.accounts.ops import invitations

    return invitations
