from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
