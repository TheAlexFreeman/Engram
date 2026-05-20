from __future__ import annotations

from typing import Protocol

from .types import SearchHit


class WebSearchBackend(Protocol):
    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        """Return ranked web results for the query."""
