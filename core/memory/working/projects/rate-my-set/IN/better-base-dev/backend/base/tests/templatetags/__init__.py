from __future__ import annotations

from backend.base.templatetags.static_for_email import static_for_email


def test_static_for_email(settings):
    static_path1 = "logos/email-logo-small.png"

    settings.BASE_BACKEND_URL = "https://example.com"
    settings.STATIC_URL = "/static/"

    assert (
        static_for_email(static_path1)
        == "https://example.com/static/logos/email-logo-small.png"
    )
