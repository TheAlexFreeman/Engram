from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.debug import sensitive_variables

from backend.accounts.ops.invitations import (
    FollowWithSecretToken,
    check_and_load_followed_invitation_data,
    restore_session_invitation_data,
)
from backend.accounts.ops.invitations import (
    follow_invitation as follow_invitation_op,
)
from backend.auth.ops.logout import perform_logout


@requires_csrf_token
@sensitive_variables("request", "secret_token", "email_signature", "follow_with")
def invitation_redirect_to_follow(
    request: HttpRequest, secret_token: str
) -> HttpResponseRedirect:
    email_signature: str | None = request.GET.get("es")
    follow_with = FollowWithSecretToken(
        secret_token=secret_token,
        email_signature=email_signature,
        should_mark_followed=True,
    )

    result = follow_invitation_op(request=request, follow_with=follow_with)

    # By default, we should log out if the request's user is authenticated.
    should_logout: bool = request.user.is_authenticated
    # However, if the found user is the same as the authenticated user, we'll keep the
    # user logged in.
    if (
        request.user.is_authenticated
        and result.found_user is not None
        and result.found_user == request.user
    ):
        should_logout = False

    if should_logout:
        # By default, Django's logout calls `request.session.flush()`. That's fine,
        # except that we want to keep any invitation-related data in the session, so
        # we'll use `restore_session_invitation_data` to mark it before logging out and
        # then restore it after so that the invitation-related session data persists
        # past this logout here.
        with restore_session_invitation_data(request=request):
            perform_logout(request=request)

    return redirect("follow-invitation")


@requires_csrf_token
def follow_invitation(request: HttpRequest) -> HttpResponse:
    check_and_load_followed_invitation_data(
        request=request, set_immediately_redirect_to=True
    )

    return render(request, "index.html")
