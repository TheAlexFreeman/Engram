from __future__ import annotations

from collections.abc import Collection
from typing import TypeVar

from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.fields import AutoCreatedField, AutoLastModifiedField
from model_utils.models import TimeStampedModel

from backend.utils.repr import nice_instance_repr

CoreModelGenericType = TypeVar("CoreModelGenericType", bound="CoreModel")


class CoreQuerySet(models.QuerySet[CoreModelGenericType]):
    pass


class CoreModel(TimeStampedModel):
    REPR_FIELDS: Collection[str] = ("pk",)

    created = AutoCreatedField(_("Created"))
    modified = AutoLastModifiedField(_("Modified"))

    class Meta:
        abstract = True
        verbose_name = _("Core Model")
        verbose_name_plural = _("Core Models")

    def __repr__(self) -> str:
        repr_fields = self.REPR_FIELDS
        if not repr_fields:
            return super().__repr__()
        return nice_instance_repr(self, repr_fields)

    def __str__(self) -> str:
        return repr(self)
