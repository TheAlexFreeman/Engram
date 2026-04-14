from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeAlias

from rest_framework.serializers import (
    BaseSerializer,
    HiddenField,
    PrimaryKeyRelatedField,
)

# --- For `ModelAttributeReadHiddenField` ---

ModelHiddenDeserializePrimaryKeyType: TypeAlias = Literal["pk"]
ModelHiddenDeserializeSerializerType: TypeAlias = BaseSerializer
ModelHiddenDeserializeCallableType: TypeAlias = Callable[[Any], Any]

ModelHiddenDeserializeType: TypeAlias = (
    ModelHiddenDeserializePrimaryKeyType
    | ModelHiddenDeserializeSerializerType
    | ModelHiddenDeserializeCallableType
)


class ModelAttributeReadHiddenField(HiddenField):
    """
    Override `HiddenField` to be `write_only=False` (default `HiddenField` is
    `write_only=True`), and, on read, access the `source` (usually equal to
    `field_name`) attribute on the model or similar instance.
    """

    def __init__(
        self, *args, deserialize: ModelHiddenDeserializeType | None = None, **kwargs
    ):
        # Take straight from REST Framework's `HiddenField` `__init__`.
        assert "default" in kwargs, "default is a required argument."

        # Grandparent inheritance, skip `write_only=True` in
        # `super(HiddenField, self)` (default `super()`).
        super(HiddenField, self).__init__(*args, **kwargs)

        self.deserialize = deserialize

    def bind(self, field_name: str, parent: BaseSerializer) -> None:
        super().bind(field_name, parent)

        # If `deserialize` is a serializer, bind it (after the `super()` call above).
        if isinstance(self.deserialize, BaseSerializer):
            output_serializer = self.deserialize
            # If `field_name` is `None` or `parent` is `None`, then we've confirmed that
            # `output_serializer` hasn't been bound yet, so we bind it. Otherwise, we
            # assume it's already been bound.
            if output_serializer.field_name is None or output_serializer.parent is None:
                output_serializer.bind(field_name, parent)

    def to_representation(self, value):
        if self.deserialize is None:
            return value
        if self.deserialize == "pk":
            return value.pk
        if isinstance(self.deserialize, BaseSerializer):
            return self.deserialize.to_representation(value)
        if callable(self.deserialize):
            return self.deserialize(value)
        raise TypeError(
            f"The `deserialize` attribute value of `{self.deserialize}` for `{self}` "
            "is not one of the supported types/values."
        )


# ---                                     ---

# --- For `WritePrimaryKeyReadSerializerRelatedField` ---


class WritePrimaryKeyReadSerializerRelatedField(PrimaryKeyRelatedField):
    def __init__(self, *args, deserialize: BaseSerializer, **kwargs):
        super().__init__(*args, **kwargs)

        if deserialize is None or not isinstance(deserialize, BaseSerializer):
            raise TypeError(
                "Incorrect type for `deserialize`. Expected a serializer (an instance "
                f"of `BaseSerializer`), but got `{deserialize}`."
            )

        self.deserialize = deserialize

    def use_pk_only_optimization(self):
        # We need the full instance for `to_representation`, so we can't use the pk-only
        # optimization.
        return False

    def bind(self, field_name: str, parent: BaseSerializer) -> None:
        super().bind(field_name, parent)

        # If `deserialize` is a serializer, bind it (after the `super()` call above).
        if isinstance(self.deserialize, BaseSerializer):
            output_serializer = self.deserialize
            # If `field_name` is `None` or `parent` is `None`, then we've confirmed that
            # `output_serializer` hasn't been bound yet, so we bind it. Otherwise, we
            # assume it's already been bound.
            if output_serializer.field_name is None or output_serializer.parent is None:
                output_serializer.bind(field_name, parent)

    def to_representation(self, value):
        if isinstance(self.deserialize, BaseSerializer):
            return self.deserialize.to_representation(value)
        raise TypeError(
            f"The `deserialize` attribute value of `{self.deserialize}` for `{self}` "
            "is not one of the supported types/values."
        )


# ---                                                 ---
