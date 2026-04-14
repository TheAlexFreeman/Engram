from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def add_query_param_to_url(url: str, key: str, value: Any) -> str:
    url_parts = urlparse(url)
    query_params = parse_qs(url_parts.query)

    query_params[key] = [value]

    new_query = urlencode(query_params, doseq=True)
    new_url_parts = list(url_parts)
    new_url_parts[4] = new_query

    return urlunparse(new_url_parts)
