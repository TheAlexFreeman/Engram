from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import Field, Model
from django.db.models.fields.related import ForeignObjectRel


def get_primary_key_field(
    model_class: type[Model],
) -> Field | ForeignObjectRel | GenericForeignKey:
    invitation_fields = model_class._meta.get_fields()
    primary_key_fields = [
        field for field in invitation_fields if getattr(field, "primary_key", False)
    ]
    assert primary_key_fields and len(primary_key_fields) == 1, "Current post-condition"
    return primary_key_fields[0]
