from __future__ import annotations

from contextlib import contextmanager

from django.db import DEFAULT_DB_ALIAS, connections, transaction


def is_in_transaction(using: str | None = None) -> bool:
    connection = connections[using or DEFAULT_DB_ALIAS]
    return connection.in_atomic_block


@contextmanager
def transaction_if_not_in_one_already(using: str | None = None):
    if is_in_transaction(using):
        yield
    else:
        with transaction.atomic(using):
            yield
