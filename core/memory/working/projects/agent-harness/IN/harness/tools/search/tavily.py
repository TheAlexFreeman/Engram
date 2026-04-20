from __future__ import annotations

import os
from typing import Any

import httpx

from ._http import parse_json, raise_for_status_short
from .types import SearchHit

_TAVILY_URL = "https://api.tavily.com/search"


class TavilyBackend:
    def __init__(self, api_key: str | None = None):
        key = (api_key if api_key is not None else os.environ.get("TAVILY_API_KEY", "")).strip()
        if not key:
            raise ValueError(
                "Tavily search requires TAVILY_API_KEY in the environment (or pass api_key=...)."
            )
        self._api_key = key

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
        }
        headers = {"Content-Type": "application/json"}
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(_TAVILY_URL, json=payload, headers=headers)
        raise_for_status_short(resp, provider="Tavily")
        data = parse_json(resp, provider="Tavily")
        return _parse_tavily_results(data, max_results)


def _parse_tavily_results(data: Any, max_results: int) -> list[SearchHit]:
    raw = data.get("results") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    hits: list[SearchHit] = []
    for item in raw:
        if len(hits) >= max_results:
            break
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or item.get("snippet") or "").strip()
        if url:
            hits.append(SearchHit(title=title or url, url=url, snippet=snippet))
    return hits
