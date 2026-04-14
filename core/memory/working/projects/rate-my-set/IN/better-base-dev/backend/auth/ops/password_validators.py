from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from backend.utils.class_properties import cached_classproperty

if TYPE_CHECKING:
    from backend.accounts.models.users import User


class AtLeastOneNumberPasswordValidator:
    """
    Validate that the password contains at least one number.
    """

    @cached_classproperty
    def re_pattern(self) -> re.Pattern:
        return re.compile(r"[0-9]")

    def validate(self, password: str, user: User | None = None) -> None:
        if not password or not self.re_pattern.search(password):
            raise ValidationError(
                _("Please include at least one number in your password"),
                code="password_missing_number",
            )

    def get_help_text(self) -> StrOrPromise:
        return _("Your password should include at least one number.")


class AtLeastOneSpecialCharacterPasswordValidator:
    """
    Validate that the password contains at least one special character.
    """

    @cached_classproperty
    def re_pattern(self) -> re.Pattern:
        return re.compile(r"[^0-9a-zA-Z]")

    def validate(self, password: str, user: User | None = None) -> None:
        if not password or not self.re_pattern.search(password):
            raise ValidationError(
                _(
                    "Please include at least one special character (!@#$&*%?) in your password"
                ),
                code="password_missing_special_character",
            )

    def get_help_text(self) -> StrOrPromise:
        return _(
            "Your password should include at least one special character (!@#$&*%?)."
        )
