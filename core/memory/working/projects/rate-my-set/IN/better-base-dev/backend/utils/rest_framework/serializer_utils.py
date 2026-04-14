from __future__ import annotations

from collections.abc import Collection


def exclude_fields(
    writable_fields: Collection[str],
    *,
    from_fields: Collection[str],
    validate_writable_in_from: bool = True,
) -> list[str]:
    final_fields: list[str] = [f for f in from_fields if f not in writable_fields]

    if validate_writable_in_from and (
        diff_set := set(writable_fields) - set(from_fields)
    ):
        raise ValueError(
            f"Fields `{diff_set}` are in `writable_fields` but not in `from_fields`. "
            "Was there a typo somewhere?"
        )

    return final_fields
