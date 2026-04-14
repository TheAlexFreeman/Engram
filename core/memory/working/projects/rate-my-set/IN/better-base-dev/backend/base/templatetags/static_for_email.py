from __future__ import annotations

from urllib.parse import quote, urljoin

from django import template
from django.conf import settings
from django.templatetags.static import PrefixNode

register = template.Library()


@register.simple_tag
def static_for_email(path: str) -> str:
    static_value = urljoin(PrefixNode.handle_simple("STATIC_URL"), quote(path))
    return resolve_full_email_url(static_value)


def resolve_full_email_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{settings.BASE_BACKEND_URL}/{path.removeprefix('/')}"
