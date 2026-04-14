from __future__ import annotations

from django.urls import path

from .views.invitations import follow_invitation, invitation_redirect_to_follow

app_name = "accounts"
urlpatterns = [
    path(
        "invitations/redirect/to-follow/<secret_token>",
        invitation_redirect_to_follow,
        name="invitations-redirect-to-follow",
    ),
    path(
        "follow-invitation",
        follow_invitation,
        name="follow-invitation",
    ),
]
