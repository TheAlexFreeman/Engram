from __future__ import annotations

from datetime import UTC, timedelta

import pytest
from django.utils import timezone

from backend.accounts.tests.factories.accounts import Account, AccountFactory
from backend.base.tests.factories.core import CoreFactory


@pytest.mark.django_db
def test_core_factory():
    # NOTE: At the time of writing, `AccountFactory` uses the `CoreFactory` under the
    # hood. Hence, we'll just use that to test this.
    factory_class = AccountFactory
    assert issubclass(factory_class, CoreFactory), "Pre-condition"

    # Pick `6` (somewhat arbitrary) values to check from `build`.
    c1 = factory_class.build()
    c2 = factory_class.build()
    c3 = factory_class.build()
    c4 = factory_class.build()
    c5 = factory_class.build()
    c6 = factory_class.build()

    # Pick `2` (somewhat arbitrary) values to check from `create`.
    c7 = factory_class.create()
    c8 = factory_class()

    now = timezone.now()

    # Give a small amount of buffer in either direction.
    created_start_at_least = now - timedelta(days=(366 * 2 + 2))
    created_end_at_most = now + timedelta(minutes=2)
    modified_end_at_most = created_end_at_most

    def check(v: Account, *, persistent: bool) -> None:
        assert v.created.tzinfo == UTC
        assert v.created >= created_start_at_least
        assert v.created <= created_end_at_most

        assert v.modified.tzinfo == UTC
        assert v.modified >= v.created
        assert v.modified <= modified_end_at_most

        if persistent:
            assert v.pk is not None
        else:
            assert v.pk is None

    check(c1, persistent=False)
    check(c2, persistent=False)
    check(c3, persistent=False)
    check(c4, persistent=False)
    check(c5, persistent=False)
    check(c6, persistent=False)

    check(c7, persistent=True)
    check(c8, persistent=True)  # type: ignore[arg-type]
