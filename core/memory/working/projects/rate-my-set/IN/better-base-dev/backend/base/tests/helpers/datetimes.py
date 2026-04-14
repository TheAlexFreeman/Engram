from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dirty_equals import IsDatetime
from django.utils.dateparse import parse_datetime


class Times:
    def __init__(self, now: datetime):
        self.now = now

        self._monotonic_now_microseconds_counter: int = 1

    @property
    def now_incremented(self) -> datetime:
        """
        Get a value close to `self.now`, but guaranteed to be monotonically increasing.
        """
        return_value = self.now + timedelta(
            microseconds=self._monotonic_now_microseconds_counter
        )

        self._monotonic_now_microseconds_counter += 1

        return return_value

    @property
    def close_to_now(self) -> IsDatetime:
        return IsDatetime(approx=self.now, delta=timedelta(minutes=3))

    def is_close_to_now(
        self, value: datetime | None, *, threshold: timedelta = timedelta(minutes=3)
    ) -> bool:
        return value is not None and (value - threshold) <= self.now <= (
            value + threshold
        )

    def CloseTo(
        self,
        value: datetime | timedelta | int | float | str,
        *,
        delta: timedelta = timedelta(minutes=3),
        string: bool | None = None,
        **kwargs: Any,
    ) -> IsDatetime:
        if string is not None:
            if "iso_string" in kwargs and kwargs["iso_string"] != string:
                raise ValueError(
                    "Cannot specify both `string` and `iso_string` in the same call "
                    "if the values differ."
                )
            kwargs["iso_string"] = string

        if isinstance(value, datetime):
            return IsDatetime(approx=value, delta=delta, **kwargs)
        elif isinstance(value, int | float):
            return self.CloseTo(timedelta(seconds=value), delta=delta, **kwargs)
        elif isinstance(value, str):
            kwargs.setdefault("iso_string", True)
            parsed_value = parse_datetime(value) or datetime.fromisoformat(value)
            return IsDatetime(approx=parsed_value, delta=delta, **kwargs)
        else:
            assert isinstance(value, timedelta), "Current pre-condition"
            approx = self.now + value
            return IsDatetime(approx=approx, delta=delta, **kwargs)
