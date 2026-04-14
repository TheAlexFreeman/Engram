from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

import pytest
from django.core.exceptions import ValidationError


@contextmanager
def raises_validation_error(
    message: str,
    *,
    partial_match: bool = False,
    code: str | None = None,
    params: Mapping[str, Any] | None = None,
):
    with pytest.raises(ValidationError) as exc_info:
        try:
            yield exc_info
        except ValidationError as e:
            if partial_match:
                assert message in e.message
            else:
                assert e.message == message
            if code is not None:
                assert e.code == code
            if params is not None:
                assert e.params == params

            raise
