from __future__ import annotations

from typing import final

from django.views.decorators.debug import sensitive_variables


@final
class WrappedSecretValue:
    """
    Rather than passing around sensitive `secret_value`s directly in the codebase, they
    will be wrapped in this class.
    """

    @sensitive_variables(
        "secret_value", "self", "self.__secret_value", "__secret_value"
    )
    def __init__(self, *, secret_value: str):
        self.__secret_value = secret_value

    @sensitive_variables(
        "secret_value", "self", "self.__secret_value", "__secret_value"
    )
    def secret_value(self):
        """
        NOTE: Django's template system will automatically call this if accessed as
        `{{ instance.secret_value }}`. That being said, if you ever switched email
        templates to some other non Django template language system you might want to
        make this a `@property` or something related, etc.
        """
        secret_value = self.__secret_value
        return secret_value
