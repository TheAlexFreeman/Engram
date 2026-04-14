from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BaseConfig(AppConfig):
    name = "backend.base"
    verbose_name = _("Base")
