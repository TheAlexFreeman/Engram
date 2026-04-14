from __future__ import annotations

from drf_spectacular.authentication import SessionScheme
from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Thanks to https://stackoverflow.com/a/30875830 for the initial implementation and
    inspiration.
    """

    def enforce_csrf(self, request: Request) -> None:
        # Intentionally don't do anything (and let the CSRF check pass).
        pass


class CsrfExemptSessionScheme(SessionScheme):
    target_class = "backend.utils.rest_framework.csrf.CsrfExemptSessionAuthentication"
    name = "CsrfExemptSessionAuthentication"
