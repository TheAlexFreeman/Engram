from __future__ import annotations

from typing import Any, Generic, TypeVar, get_args

from django.db.models import Model
from factory.base import FactoryMetaClass
from factory.django import DjangoModelFactory

T = TypeVar("T", bound=Model)


class BaseDjangoModelFactoryMeta(FactoryMetaClass):
    """
    Thanks initially to
    https://github.com/FactoryBoy/factory_boy/issues/468#issuecomment-1536373442 -
    Initially copied on 2024-08-11, and then made a significant number of modifications
    to where it's quite different from the original source reference.
    """

    def __new__(mcs, class_name, bases: list[type], attrs):
        orig_bases = attrs.get("__orig_bases__", [])

        for t in orig_bases:
            try:
                type_args = get_args(t)
            except Exception:
                continue

            if len(type_args) != 1:
                continue
            type_arg = type_args[0]

            if "Meta" not in attrs:
                attrs["Meta"] = type("Meta", (), {})
            Meta = attrs["Meta"]

            if isinstance(type_arg, TypeVar):
                pass
            else:
                try:
                    if issubclass(type_arg, Model):
                        if (
                            type_subclass_helper_attr_value := getattr(
                                type_arg, "_FACTORY_IS_TYPE_SUBCLASS_HELPER_FOR_", None
                            )
                        ) is None:
                            Meta.model = type_arg
                        else:
                            assert issubclass(type_subclass_helper_attr_value, Model), (
                                "Current pre-condition: "
                                f"`{type_subclass_helper_attr_value}` should be a "
                                "subclass of `Model`."
                            )
                            Meta.model = type_subclass_helper_attr_value
                except TypeError:
                    pass

        return super().__new__(mcs, class_name, bases, attrs)


class BaseDjangoModelFactory(
    DjangoModelFactory, Generic[T], metaclass=BaseDjangoModelFactoryMeta
):
    class Meta:
        abstract = True

    @classmethod
    def create(cls, **kwargs: Any) -> T:
        return super().create(**kwargs)

    @classmethod
    def create_batch(cls, size: int, **kwargs: Any) -> list[T]:
        return super().create_batch(size, **kwargs)

    @classmethod
    def build(cls, **kwargs: Any) -> T:
        return super().build(**kwargs)

    @classmethod
    def build_batch(cls, size: int, **kwargs: Any) -> list[T]:
        return super().build_batch(size, **kwargs)

    @classmethod
    def stub(cls, **kwargs: Any) -> T:
        return super().stub(**kwargs)

    @classmethod
    def stub_batch(cls, size: int, **kwargs: Any) -> list[T]:
        return super().stub_batch(size, **kwargs)
