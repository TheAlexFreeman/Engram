from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from functools import partial
from typing import Any, TypeAlias, TypeVar

# NOTE: `DL` stands here for "Dictionary or list".
DL = TypeVar("DL", dict[Any, Any], list[Any])

DeepKeyValueTransformFuncReturnType: TypeAlias = (
    tuple[Any, Any] | list[tuple[Any, Any]] | None
)


def json_like_dict_deep_key_value_transform(
    d: DL,
    func: Callable[[tuple[Any, Any]], DeepKeyValueTransformFuncReturnType],
    *,
    mutate_in_place: bool,
    copier: Callable[[DL], DL] = deepcopy,
    _depth: int = 0,
) -> DL:
    """
    Iterate through the `dict` `d` as follows:
    * Visit all nested `dict`s.
    * Visit all nested `list`s.

    Then, for each key/value pair within any `dict` or nested `dict` found iterating as
    above, call `func((key, value))` on it.

    The return value of the `func((key, value))` call should return either:
    1. A 2-`tuple` of `(new_key, new_value)`.
    2. A list of 2-`tuple`s of `(new_key, new_value)`. This is useful for when you want
       to replace a single key/value pair with multiple key/value pairs.
    3. ^ Similar to the above, An empty list. This is useful for when you want to remove
       a key/value pair.
    4. `None` to skip removing or replacing the key/value pair. This meant to indicate
       "don't do anything", etc.
    """
    recurse = partial(
        json_like_dict_deep_key_value_transform,
        func=func,
        mutate_in_place=mutate_in_place,
        copier=copier,
        _depth=_depth + 1,
    )

    if _depth == 0 and not mutate_in_place:
        d = copier(d)

    if isinstance(d, dict):
        for t in list(d.items()):
            k, v = t
            result = func(t)
            if isinstance(result, tuple) and len(result) == 2:
                if result is not None and t != result:
                    new_k, new_v = result
                    if new_k != k:
                        d.pop(k)
                    d[new_k] = new_v
            elif isinstance(result, list):
                saw_eq_k = False
                for new_t in result:
                    if result is not None:
                        new_k, new_v = new_t
                        if new_k == k:
                            saw_eq_k = True
                    if result is None or new_t == t:
                        continue
                    d[new_k] = new_v
                if not saw_eq_k:
                    d.pop(k)
            elif result is not None:
                raise TypeError(
                    f"Unexpected return value type from `func({t!r})`: `{type(result)!r}`"
                )
        for _k, v in d.items():
            if isinstance(v, dict | list):
                recurse(v)  # type: ignore[arg-type]
    elif isinstance(d, list):
        for v in d:
            if isinstance(v, dict | list):
                recurse(v)  # type: ignore[arg-type]

    return d
