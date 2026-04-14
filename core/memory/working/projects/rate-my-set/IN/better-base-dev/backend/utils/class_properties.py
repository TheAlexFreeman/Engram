from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from types import GenericAlias
from typing import Any, Generic, Self, TypeVar, overload
from weakref import WeakKeyDictionary

T = TypeVar("T")

_NOT_FOUND = object()


class cached_classproperty(Generic[T]):
    func: Callable[[Any], T]
    attrname: str | None

    _cache: WeakKeyDictionary
    _lock: RLock

    def __init__(self, func: Callable[[Any], T]) -> None:
        self.func = func
        self.attrname = None
        self.__doc__ = func.__doc__

        self._cache = WeakKeyDictionary()
        self._lock = RLock()

    def __set_name__(self, owner: type[Any], name: str) -> None:
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_classproperty to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    @overload
    def __get__(self, instance: None, owner: None) -> Self: ...

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> T: ...

    @overload
    def __get__(self, instance: object, owner: type[Any]) -> T: ...

    def __get__(self, instance, owner=None):
        if instance is None and owner is None:
            return self

        if self.attrname is None:
            raise TypeError(
                "Cannot use this `cached_classproperty` instance without calling "
                "`__set_name__` on it."
            )

        cache = self._cache
        object_type = type(instance) if owner is None else owner

        value = cache.get(object_type, _NOT_FOUND)
        if value is _NOT_FOUND:
            with self._lock:
                # Check if another thread filled the cache while we waited for the lock.
                value = cache.get(object_type, _NOT_FOUND)
                if value is _NOT_FOUND:
                    value = self.func(object_type)
                    cache[object_type] = value

        return value

    __class_getitem__ = classmethod(GenericAlias)  # type: ignore[var-annotated]
