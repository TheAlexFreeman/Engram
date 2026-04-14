from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from backend.base.models.core import CoreModel


class ConcreteCoreModelForTests(CoreModel):
    REPR_FIELDS = ("pk", "created", "modified")

    class Meta:
        verbose_name = _("Concrete Core Model for Tests")
        verbose_name_plural = _("Concrete Core Models for Tests")
