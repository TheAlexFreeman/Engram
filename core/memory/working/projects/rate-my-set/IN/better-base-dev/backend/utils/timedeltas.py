from __future__ import annotations

from datetime import timedelta
from string import Formatter
from typing import Literal


def strfdelta(
    td: timedelta | int | float,
    fmt: str = "{D:02}d {H:02}h {M:02}m {S:02}s",
    input_type: Literal[
        "timedelta",
        "s",
        "seconds",
        "m",
        "minutes",
        "h",
        "hours",
        "d",
        "days",
        "w",
        "weeks",
    ] = "timedelta",
) -> str:
    """
    Thanks to https://stackoverflow.com/a/42320260 (last retrieved/checked on
    2024-06-18). I modified some of the variable names and added type annotations and a
    couple tests in `test_timedeltas.py`.

    Convert a datetime.timedelta object or a regular number to a custom- formatted
    string, just like the stftime() method does for datetime.datetime objects.

    The fmt argument allows custom formatting to be specified. Fields can include
    seconds, minutes, hours, days, and weeks. Each field is optional.

    Some examples:
        '{D:02}d {H:02}h {M:02}m {S:02}s' --> '05d 08h 04m 02s' (default)
        '{W}w {D}d {H}:{M:02}:{S:02}'     --> '4w 5d 8:04:02'
        '{D:2}d {H:2}:{M:02}:{S:02}'      --> ' 5d  8:04:02'
        '{H}h {S}s'                       --> '72h 800s'

    The input_type argument allows `td` to be a regular number instead of the default,
    which is a datetime.timedelta object. Valid input_type strings:
        's', 'seconds',
        'm', 'minutes',
        'h', 'hours',
        'd', 'days',
        'w', 'weeks'
    """

    # Convert `td` to integer seconds.
    if input_type == "timedelta":
        remainder = int(td.total_seconds())  # type: ignore[union-attr]
    elif input_type in ["s", "seconds"]:
        remainder = int(td)  # type: ignore[arg-type]
    elif input_type in ["m", "minutes"]:
        remainder = int(td) * 60  # type: ignore[arg-type]
    elif input_type in ["h", "hours"]:
        remainder = int(td) * 3600  # type: ignore[arg-type]
    elif input_type in ["d", "days"]:
        remainder = int(td) * 86400  # type: ignore[arg-type]
    elif input_type in ["w", "weeks"]:
        remainder = int(td) * 604800  # type: ignore[arg-type]

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ("W", "D", "H", "M", "S")
    constants = {"W": 604800, "D": 86400, "H": 3600, "M": 60, "S": 1}
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])
    return f.format(fmt, **values)
