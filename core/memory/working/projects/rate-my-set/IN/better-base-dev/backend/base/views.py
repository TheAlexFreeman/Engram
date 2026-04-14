from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token


@requires_csrf_token
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")


@requires_csrf_token
def fallback(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")
