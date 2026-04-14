from __future__ import annotations

import re


def sanitize_filename_for_storage(filename: str) -> str:
    value = re.sub(r"[^0-9a-zA-Z_\-\.\ ]", "", filename)
    value = value.replace(" ", "_")

    if "." not in value:
        return value.casefold()

    pre_ext, post_ext = value.rsplit(".", 1)
    return f"{pre_ext.replace('.', '').casefold()}.{post_ext.casefold()}"
