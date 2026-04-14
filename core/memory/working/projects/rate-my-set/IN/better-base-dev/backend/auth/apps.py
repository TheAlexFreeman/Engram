from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuthConfig(AppConfig):
    # NOTE: Have to set the `label` here explicitly because otherwise the default
    # generated `label` of `"auth"` (from `"backend.auth"`) will conflict with the
    # built-in `django.contrib.auth` app and label.
    label = "our_auth"
    name = "backend.auth"
    verbose_name = _("Authentication and Related")
