"""
* NOTE: This is a relatively special/unique file/module. We register
some extra files for pytest assertion rewriting (I.E., see
https://docs.pytest.org/en/7.1.x/how-to/assert.html#assertion-introspection-details) and
provide some useful imports. With how we do some of the lazy attribute access here, we
We also define an `__all__` for a few reasons, one of which is that `gf` is a lazily
loaded attribute.
"""

# flake8: noqa: E402
# ruff: noqa: E402
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

import pytest

pytest.register_assert_rewrite("backend.base.tests.helpers.auth")
pytest.register_assert_rewrite("backend.base.tests.helpers.datetimes")
pytest.register_assert_rewrite("backend.base.tests.helpers.emails")
pytest.register_assert_rewrite("backend.base.tests.helpers.images")
pytest.register_assert_rewrite(
    "backend.base.tests.helpers.initial_server_data_provided_for_web"
)
pytest.register_assert_rewrite("backend.base.tests.helpers.validation_errors")

from .shared import fake, is_random_seed_set_from_settings, random, random_seed

if TYPE_CHECKING:
    from backend.base.tests.factories.helpers import get_factory

    gf = get_factory
    _gf = gf
else:
    # NOTE: When imported, will be set to `get_factory` from
    # `backend.base.tests.factories.helpers`.
    _gf = None


__all__ = [
    "fake",
    "gf",
    "is_random_seed_set_from_settings",
    "random",
    "random_seed",
]


@lru_cache(1)
def _get_gf():
    """
    Set `_gf` to `get_factory` if it's not already set to that, and return the properly
    set `_gf`.
    """
    global _gf

    from backend.base.tests.factories.helpers import get_factory

    # Set `_gf` to `get_factory` if it's not already set to that.
    if _gf is None:
        _gf = get_factory  # type: ignore[unreachable]

    return get_factory


def __dir__() -> list[str]:
    """
    Module-level `__dir__`. See https://www.python.org/dev/peps/pep-0562/

    Do what the default `__dir__` would do except also make sure we've loaded `_gf`
    first.
    """
    if _gf is None:
        _get_gf()  # type: ignore[unreachable]

    return sorted(__all__)


def __getattr__(name: str) -> Any:
    """
    Module level `__getattr__`. See https://www.python.org/dev/peps/pep-0562/

    Do what the default `__getattr__` would do for everything except `_gf`, where
    we'll make sure we've loaded `_gf` first and then return it as normal.
    """
    if name == "gf":
        return _get_gf()

    if name in (globals_dict := globals()):
        return globals_dict[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}.")
