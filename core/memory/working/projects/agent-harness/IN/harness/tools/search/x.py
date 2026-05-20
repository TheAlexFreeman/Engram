from __future__ import annotations

import os
from typing import Any

import httpx

from ._http import parse_json, raise_for_status_short
from .brave import BraveBackend
from .types import SearchHit


class XSearchBackend:
    """Backend for searching X (Twitter). Uses Brave search with strong X bias.
    When GROK_API_KEY is available, future versions can leverage xAI's native x_search.
    """

    def __init__(self, api_key: str | None = None):
        # Use provided key or fall back to env. Brave is excellent for real-time X coverage.
        brave_key = api_key or os.getenv("BRAVE_API_KEY")
        if not brave_key:
            # Graceful degradation if no key (for environments where search is optional)
            from .factory import NoOpBackend
            self._brave = NoOpBackend()
        else:
            self._brave = BraveBackend(api_key=brave_key)

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        """Search X posts. Automatically enhances query for X content and uses Brave backend
        (which has excellent real-time coverage of X/Twitter)."""
        x_query = self._enhance_for_x(query)
        # Brave backend returns results that work very well for X content
        return self._brave.search(x_query, max_results=max_results, timeout_sec=timeout_sec)

    def _enhance_for_x(self, query: str) -> str:
        """Add operators to bias results toward X/Twitter content."""
        q = query.strip()
        if any(x in q.lower() for x in ["site:x.com", "site:twitter.com", "from:", "@", "#"]):
            return q  # already has X operators
        # Add strong X bias
        return f"{q} (site:x.com OR site:twitter.com OR from:x OR from:twitter)"


def _parse_x_results(data: Any, max_results: int) -> list[SearchHit]:
    """Optional specialized parser for X-specific fields (author, date, engagement).
    Currently delegates to Brave parser but can be extended."""
    # For now, reuse Brave parsing which works well for X results
    from .brave import _parse_brave_web

    return _parse_brave_web(data, max_results)
