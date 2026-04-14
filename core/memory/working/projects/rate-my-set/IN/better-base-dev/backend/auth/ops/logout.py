from __future__ import annotations

from django.contrib.auth import logout
from django.http import HttpRequest


def attempt_logout(*, request: HttpRequest) -> None:
    perform_logout(request=request)


def perform_logout(*, request: HttpRequest) -> None:
    logout(request)
