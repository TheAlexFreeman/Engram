from __future__ import annotations

from collections.abc import Collection
from typing import Final
from weakref import WeakKeyDictionary

import structlog

logger = structlog.stdlib.get_logger()


def nice_instance_repr(instance: object, repr_fields: Collection[str]) -> str:
    key_value_pairs: list[tuple[str, str]] = []
    for attribute_name in repr_fields:
        field_value = getattr(instance, attribute_name, "<MISSING_ATTRIBUTE>")
        if field_value == "<MISSING_ATTRIBUTE>":
            _check_and_maybe_log_missing_attr(type(instance), attribute_name)
        key_value_pairs.append((attribute_name, repr(field_value)))
    class_name = instance.__class__.__name__
    inner_str = ", ".join(f"{key}={value}" for key, value in key_value_pairs)
    return f"{class_name}({inner_str})"


class NiceReprMixin:
    REPR_FIELDS: Collection[str] = ()

    def __repr__(self) -> str:
        repr_fields = self.REPR_FIELDS
        if not repr_fields:
            return super().__repr__()
        return nice_instance_repr(self, repr_fields)

    def __str__(self) -> str:
        return repr(self)


_missing_attr_types: WeakKeyDictionary[type, set[str]] = WeakKeyDictionary()
_missing_attr_types_max_num_keys: Final[int] = 128
_missing_attr_types_max_num_values_per_key: Final[int] = 16


def _check_and_maybe_log_missing_attr(instance: object, attribute_name: str) -> None:
    instance_type = type(instance)
    logged_attrs = _missing_attr_types.get(instance_type) or set()

    if not logged_attrs or attribute_name not in logged_attrs:
        logged_attrs.add(attribute_name)
        _missing_attr_types[instance_type] = set()

        logger.error(
            "Missing attribute for `REPR_FIELDS`.",
            attribute_name=attribute_name,
            instance=instance,
            instance_type=instance_type,
        )

    if len(logged_attrs) > _missing_attr_types_max_num_values_per_key:
        logger.error(
            (
                "Exceeded max number of values per-key for missing `REPR_FIELDS` "
                "attributes. Clearing."
            ),
            max_num=_missing_attr_types_max_num_values_per_key,
            attribute_names=logged_attrs,
            triggering_attribute_name=attribute_name,
            triggering_instance=instance,
            triggering_instance_type=instance_type,
        )
        logged_attrs.clear()

    if len(_missing_attr_types) > _missing_attr_types_max_num_keys:
        logger.error(
            (
                "Exceeded max number of keys for missing `REPR_FIELDS` attributes "
                "instances. Clearing."
            ),
            max_num=_missing_attr_types_max_num_keys,
            triggering_attribute_name=attribute_name,
            triggering_instance=instance,
            triggering_instance_type=instance_type,
        )
        _missing_attr_types.clear()
