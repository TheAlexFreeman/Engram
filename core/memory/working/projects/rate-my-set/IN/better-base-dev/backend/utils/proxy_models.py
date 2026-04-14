from __future__ import annotations

from django.db.models import Model


def get_proxy_source_model(model_class: type[Model]) -> type[Model]:
    if model_class._meta.proxy:
        return get_proxy_source_model(model_class._meta.proxy_for_model)  # type: ignore[arg-type]
    return model_class
