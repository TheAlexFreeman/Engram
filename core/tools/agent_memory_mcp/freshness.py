"""Freshness scoring for memory retrieval ranking.

Provides a shared exponential-decay freshness score computed from file
frontmatter dates.  Used by ``memory_search`` (text search) and available
for future semantic search tools.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

# Default half-life in days — after this many days the freshness score
# drops to 0.5.  Matches the medium-trust flagging threshold in
# core/INIT.md (Exploration stage).
DEFAULT_HALF_LIFE_DAYS = 180


def parse_date(value: Any) -> date | None:
    """Best-effort parse of a frontmatter date value.

    Handles ``datetime.date``, ``datetime.datetime``, and ISO-format strings.
    Returns ``None`` when parsing fails or the value is falsy.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def effective_date(frontmatter: dict[str, Any]) -> date | None:
    """Return the most relevant date for freshness scoring.

    Prefers ``last_verified``, then falls back to ``created``.
    """
    d = parse_date(frontmatter.get("last_verified"))
    if d is not None:
        return d
    return parse_date(frontmatter.get("created"))


def freshness_score(
    ref_date: date | None,
    *,
    today: date | None = None,
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Compute an exponential-decay freshness score in [0, 1].

    A file verified/created *today* scores 1.0.  After *half_life_days* the
    score is 0.5, after 2× it is 0.25, etc.

    Returns 0.0 when *ref_date* is ``None`` (unknown date) or in the future
    (clamped to 1.0 would also be reasonable, but 0.0 is more conservative
    for unknowns).
    """
    if ref_date is None:
        return 0.0
    if today is None:
        today = date.today()
    age_days = (today - ref_date).days
    if age_days < 0:
        # Future date — treat as perfectly fresh
        return 1.0
    if half_life_days <= 0:
        return 1.0 if age_days == 0 else 0.0
    decay = math.log(2) / half_life_days
    return math.exp(-decay * age_days)
