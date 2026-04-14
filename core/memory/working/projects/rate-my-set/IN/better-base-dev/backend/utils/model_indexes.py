from __future__ import annotations

from collections.abc import Collection
from typing import Any

from django.contrib.postgres.indexes import BrinIndex
from django.db.models import Index

from backend.utils.databases import is_db_postgresql

_BrinOrFallbackIndexBase = BrinIndex if is_db_postgresql() else Index


class BrinOrFallbackIndex(_BrinOrFallbackIndexBase):  # type: ignore[valid-type,misc]
    def __init__(
        self,
        *expressions,
        autosummarize: bool | None = None,
        pages_per_range: int | None = None,
        fields: Collection[str] = (),
        name: str | None = None,
        **kwargs: Any,
    ):
        if isinstance(self, BrinIndex):
            super().__init__(
                *expressions,
                autosummarize=autosummarize,
                pages_per_range=pages_per_range,
                fields=fields,
                name=name,
                **kwargs,
            )
        else:
            super().__init__(
                *expressions,
                fields=fields,
                name=name,
                **kwargs,
            )
