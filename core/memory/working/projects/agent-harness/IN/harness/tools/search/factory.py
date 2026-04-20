from __future__ import annotations

import os

from .backends import WebSearchBackend
from .bing import BingBackend
from .brave import BraveBackend
from .tavily import TavilyBackend
from .types import SearchHit
from .x import XSearchBackend


class NoOpBackend:
    """Search disabled via HARNESS_SEARCH_DISABLED=1 — returns a single explanatory pseudo-hit."""

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        return [
            SearchHit(
                title="Web search disabled",
                url="about:blank",
                snippet=(
                    "Set HARNESS_SEARCH_DISABLED to 0 or unset it, and configure "
                    "HARNESS_SEARCH_PROVIDER with the matching API keys (see web_search tool description)."
                ),
            )
        ]


def load_backend_from_env() -> WebSearchBackend:
    """
    Select a search backend from the environment.

    - HARNESS_SEARCH_DISABLED: if ``1``, ``true``, or ``yes`` (case-insensitive), returns NoOpBackend.
    - HARNESS_SEARCH_PROVIDER: ``brave`` (default), ``tavily``, or ``bing``.
    - Keys: BRAVE_API_KEY, TAVILY_API_KEY, or AZURE_BING_SEARCH_KEY (+ optional AZURE_BING_SEARCH_ENDPOINT).
    """
    disabled = os.environ.get("HARNESS_SEARCH_DISABLED", "").strip().lower()
    if disabled in ("1", "true", "yes", "on"):
        return NoOpBackend()

    provider = os.environ.get("HARNESS_SEARCH_PROVIDER", "brave").strip().lower() or "brave"
    if provider == "brave":
        return BraveBackend()
    if provider == "tavily":
        return TavilyBackend()
    if provider == "bing":
        return BingBackend()
    if provider in ("x", "twitter", "xsearch"):
        return XSearchBackend()
    raise ValueError(
        f"Unknown HARNESS_SEARCH_PROVIDER={provider!r}. "
        f"Use brave, tavily, bing, or x (for X/Twitter search)."
    )
