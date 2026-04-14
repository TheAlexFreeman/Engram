from __future__ import annotations

from django.forms import BaseInlineFormSet


class BaseInlineFormSetWithLimit(BaseInlineFormSet):
    limit_number: int | None = None

    def __init_subclass__(
        cls, *args, limit_number: int | None = None, **kwargs
    ) -> None:
        if limit_number is not None:
            cls.limit_number = limit_number

        super().__init_subclass__(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        assert self.limit_number is not None, (
            "Pre-condition: `limit_number` should have been specified in the subclass "
            "either as a class attribute or through the `__init_subclass__` machinery."
        )

        if self.queryset is not None:
            self.queryset = self.queryset[: self.limit_number]
