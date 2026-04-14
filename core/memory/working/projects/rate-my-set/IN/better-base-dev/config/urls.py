from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views import defaults as default_views
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from backend.accounts.views.invitations import follow_invitation
from backend.base.views import fallback, home

# Base/Main URLs
urlpatterns = [
    path("", home, name="home"),
    path("accounts/", include("backend.accounts.urls")),
    path("auth/", include("backend.auth.urls")),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    #
    # Your stuff: custom urls includes go here
    #
    # Invitations
    #
    # ! Important NOTE: At the time of writing, this is here to match the frontend web
    # app's URL exactly. So, DO NOT change this URL without changing the frontend web
    # app's URL, etc.
    path(
        "follow-invitation",
        follow_invitation,
        name="follow-invitation",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# API URLs
urlpatterns += [
    # API base url
    path("api/", include("config.api_router")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]

# Debug URLs
if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit these
    # url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]

    # Django Debug Toolbar URLs
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns

urlpatterns += [re_path(r"^(?!api\/.*$).*", fallback, name="fallback")]
