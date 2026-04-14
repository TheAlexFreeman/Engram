from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from django.db import transaction


@contextmanager
def auto_rolling_back_transaction() -> Generator[None]:
    try:
        with transaction.atomic():
            yield
            raise _TriggerRollback
    except _TriggerRollback:
        pass


class _TriggerRollback(Exception):
    pass
