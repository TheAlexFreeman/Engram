from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx

from ._http import parse_json, raise_for_status_short
from .types import SearchHit

_DEFAULT_BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


class BingBackend:
    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        key = (api_key if api_key is not None else os.environ.get("AZURE_BING_SEARCH_KEY", "")).strip()
        if not key:
            raise ValueError(
                "Bing search requires AZURE_BING_SEARCH_KEY in the environment (or pass api_key=...)."
            )
        ep = (endpoint if endpoint is not None else os.environ.get("AZURE_BING_SEARCH_ENDPOINT", "")).strip()
        self._endpoint = ep or _DEFAULT_BING_ENDPOINT
        self._api_key = key

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        sep = "&" if "?" in self._endpoint else "?"
        url = f"{self._endpoint}{sep}{urlencode({'q': query, 'count': str(max_results)})}"
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(url, headers=headers)
        raise_for_status_short(resp, provider="Bing")
        data = parse_json(resp, provider="Bing")
        return _parse_bing_web_pages(data, max_results)


def _parse_bing_web_pages(data: Any, max_results: int) -> list[SearchHit]:
    web = data.get("webPages") if isinstance(data, dict) else None
    raw = web.get("value") if isinstance(web, dict) else None
    if not isinstance(raw, list):
        return []
    hits: list[SearchHit] = []
    for item in raw:
        if len(hits) >= max_results:
            break
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if url:
            hits.append(SearchHit(title=title or url, url=url, snippet=snippet))
    return hits
