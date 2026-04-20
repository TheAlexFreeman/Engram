from __future__ import annotations

import os
from typing import Any

import httpx

from ._http import parse_json, raise_for_status_short
from .types import SearchHit

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveBackend:
    def __init__(self, api_key: str | None = None):
        key = (api_key if api_key is not None else os.environ.get("BRAVE_API_KEY", "")).strip()
        if not key:
            raise ValueError(
                "Brave search requires BRAVE_API_KEY in the environment (or pass api_key=...)."
            )
        self._api_key = key

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        params = {"q": query, "count": str(max_results)}
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(_BRAVE_URL, params=params, headers=headers)
        raise_for_status_short(resp, provider="Brave")
        data = parse_json(resp, provider="Brave")
        return _parse_brave_web(data, max_results)


def _parse_brave_web(data: Any, max_results: int) -> list[SearchHit]:
    web = data.get("web") if isinstance(data, dict) else None
    raw_results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(raw_results, list):
        return []
    hits: list[SearchHit] = []
    for item in raw_results:
        if len(hits) >= max_results:
            break
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("description") or "").strip()
        if not snippet and isinstance(item.get("extra_snippets"), list):
            parts = [str(x).strip() for x in item["extra_snippets"] if str(x).strip()]
            if parts:
                snippet = " ".join(parts[:2])
        if url:
            hits.append(SearchHit(title=title or url, url=url, snippet=snippet))
    return hits
