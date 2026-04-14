from __future__ import annotations

import json
from typing import Any, TypedDict, cast

from django.core.serializers import serialize
from django.db.models import Model


class SerializeOneModelInstanceToJsonDictResult(TypedDict):
    model: str
    pk: Any
    fields: dict[str, Any]


def serialize_one_model_instance_to_json_dict(
    instance: Model, exclude_fields: list[str] | None = None
) -> SerializeOneModelInstanceToJsonDictResult:
    value_str = serialize(
        "json",
        [instance],
    )
    value = json.loads(value_str)[0]
    fields = value["fields"]

    if exclude_fields is not None:
        for field in exclude_fields:
            del fields[field]

    return cast(SerializeOneModelInstanceToJsonDictResult, value)
