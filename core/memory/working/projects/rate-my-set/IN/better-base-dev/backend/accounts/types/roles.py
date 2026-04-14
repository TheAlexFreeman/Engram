from __future__ import annotations

from typing import Final

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class Role(TextChoices):
    MEMBER = "member", _("Member")
    OWNER = "owner", _("Owner")


# NOTE: At the time of writing, this is used to help order `Account` `Membership`s by
# role where `OWNER`s are first, then `MEMBER`s, etc.
role_priority_mapping: Final[dict[Role, int]] = {
    Role.OWNER: 2,
    Role.MEMBER: 1,
}

assert sorted(map(str, role_priority_mapping.keys())) == sorted(map(str, [*Role])), (
    "Pre-condition: You must include every enum value in `Role` in "
    "`role_priority_mapping`."
)
assert sorted(role_priority_mapping.values()) == list(
    range(1, len(role_priority_mapping) + 1)
), "Current pre-condition: `role_priority_mapping` should have 1...n as the values."
