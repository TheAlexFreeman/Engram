"""Shared provenance/frontmatter contract constants and validators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError

REQUIRED_FRONTMATTER_KEYS: tuple[str, ...] = (
    "source",
    "origin_session",
    "created",
    "trust",
)

SOURCE_VALUE_ORDER: tuple[str, ...] = (
    "user-stated",
    "agent-inferred",
    "agent-generated",
    "external-research",
    "skill-discovery",
    "template",
    "unknown",
)
ALLOWED_SOURCE_VALUES: frozenset[str] = frozenset(SOURCE_VALUE_ORDER)

TRUST_VALUE_ORDER: tuple[str, ...] = ("high", "medium", "low")
ALLOWED_TRUST_VALUES: frozenset[str] = frozenset(TRUST_VALUE_ORDER)


def validate_frontmatter_metadata(
    frontmatter: Mapping[str, Any],
    *,
    context: str = "frontmatter",
    require_required_keys: bool = True,
) -> None:
    """Validate provenance keys and vocabularies for a parsed frontmatter mapping."""
    missing = [
        key
        for key in REQUIRED_FRONTMATTER_KEYS
        if key not in frontmatter or frontmatter.get(key) in (None, "")
    ]
    if require_required_keys and missing:
        raise ValidationError(
            f"{context} is missing required provenance fields: {', '.join(missing)}"
        )

    source = frontmatter.get("source")
    if source is not None and source not in ALLOWED_SOURCE_VALUES:
        raise ValidationError(
            f"{context} has invalid source {source!r}; allowed values: {list(SOURCE_VALUE_ORDER)!r}"
        )

    trust = frontmatter.get("trust")
    if trust is not None and trust not in ALLOWED_TRUST_VALUES:
        raise ValidationError(
            f"{context} has invalid trust {trust!r}; allowed values: {list(TRUST_VALUE_ORDER)!r}"
        )


def validate_trust_boundary(
    frontmatter: Mapping[str, Any], *, context: str = "frontmatter"
) -> None:
    """Require explicit approval for trust:high assignments outside user-stated facts."""
    trust = frontmatter.get("trust")
    source = frontmatter.get("source")
    if trust == "high" and source != "user-stated":
        raise ValidationError(
            f"{context} sets trust:high with source {source!r}; user confirmation is required"
        )


__all__ = [
    "ALLOWED_SOURCE_VALUES",
    "ALLOWED_TRUST_VALUES",
    "REQUIRED_FRONTMATTER_KEYS",
    "SOURCE_VALUE_ORDER",
    "TRUST_VALUE_ORDER",
    "validate_frontmatter_metadata",
    "validate_trust_boundary",
]
