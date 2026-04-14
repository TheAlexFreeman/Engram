from __future__ import annotations

from datetime import timedelta

from backend.utils.timedeltas import strfdelta


def test_strfdelta():
    """
    Thanks to the demo from https://stackoverflow.com/a/42320260.
    """
    td = timedelta(days=2, hours=3, minutes=5, seconds=8, microseconds=340)

    assert strfdelta(td) == "02d 03h 05m 08s"

    assert strfdelta(td, "{D}d {H}:{M:02}:{S:02}") == "2d 3:05:08"

    assert strfdelta(td, "{D:2}d {H:2}:{M:02}:{S:02}") == " 2d  3:05:08"

    assert strfdelta(td, "{H}h {S}s") == "51h 308s"

    assert strfdelta(12304, input_type="s") == "00d 03h 25m 04s"

    assert strfdelta(620, "{H}:{M:02}", "m") == "10:20"

    assert strfdelta(49, "{D}d {H}h", "h") == "2d 1h"

    # Added some of my own test case(s).
    assert strfdelta(timedelta(minutes=1, seconds=32), "{M}m {S}s") == "1m 32s"
    assert strfdelta(timedelta(seconds=45), "{M}m {S}s") == "0m 45s"
    assert strfdelta(timedelta(seconds=8), "{S}s") == "8s"
    assert strfdelta(timedelta(seconds=8, microseconds=205), "{M}m {S}s") == "0m 8s"
