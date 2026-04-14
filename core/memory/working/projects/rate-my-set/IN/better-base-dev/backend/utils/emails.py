from __future__ import annotations

import re


def parse_just_email_from_email_or_name_and_email_string(s: str) -> str:
    if match := re.match(r"^([^\@]+)\<([^\@]+\@[^\@]+)>$", s):
        return match.group(2)
    return s
