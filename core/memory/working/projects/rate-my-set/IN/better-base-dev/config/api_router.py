from __future__ import annotations

from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from backend.accounts.api.views.accounts import AccountViewSet
from backend.accounts.api.views.invitations import InvitationViewSet
from backend.accounts.api.views.memberships import MembershipViewSet
from backend.accounts.api.views.users import UserViewSet
from backend.auth.api.views.auth import AuthViewSet

router: SimpleRouter
if settings.DEBUG:
    router = DefaultRouter(trailing_slash=False)
else:
    router = SimpleRouter(trailing_slash=False)

router.register("auth", AuthViewSet, basename="auth")
router.register("invitations", InvitationViewSet, basename="invitations")
router.register("users", UserViewSet, basename="users")
router.register("accounts", AccountViewSet, basename="accounts")
router.register("memberships", MembershipViewSet, basename="memberships")

app_name = "api"
urlpatterns = [*router.urls]
