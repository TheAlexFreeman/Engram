from __future__ import annotations

import json
from json import JSONEncoder
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import SafeString, mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer


def prettify_json_as_html(
    json_like: dict[str, Any],
    *,
    sort_keys: bool = True,
    indent: int = 2,
    cls: type[JSONEncoder] = DjangoJSONEncoder,
    truncate_at: int | None = None,
    # See available styles, try `from pygments.styles import STYLE_MAP`. Also, see
    # https://pygments.org/docs/styles/.
    style: str = "default",
) -> SafeString:
    """
    Thanks to https://daniel.feldroy.com/posts/pretty-formatting-json-django-admin
    """
    dump_result = json.dumps(json_like, sort_keys=sort_keys, indent=indent, cls=cls)

    if truncate_at is not None:
        # Thanks to https://www.compart.com/en/unicode/U+2026
        # Unicode Character “…” (U+2026)
        horizontal_ellipsis_char = "…"
        dump_result = dump_result[:truncate_at] + horizontal_ellipsis_char

    formatter = HtmlFormatter(style=style)
    formatted = highlight(dump_result, JsonLexer(), formatter)
    style_def = "<style>" + formatter.get_style_defs() + "</style><br>"

    return mark_safe(style_def + formatted)
