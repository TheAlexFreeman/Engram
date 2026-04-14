from __future__ import annotations

from django.db.models import Model


def is_inserting(model: Model) -> bool:
    return model.pk is None or model._state.adding
