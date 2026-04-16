"""Platform-specific transcript parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .claude_code import ClaudeCodeTranscriptParser

if TYPE_CHECKING:
    from ..parser import TranscriptParser

# Priority order: first match wins for auto platform selection when scanning.
PARSER_REGISTRY: dict[str, type[ClaudeCodeTranscriptParser]] = {
    "claude-code": ClaudeCodeTranscriptParser,
}
PARSER_PRIORITY: tuple[str, ...] = tuple(PARSER_REGISTRY.keys())


def build_parsers_from_registry(platform: str) -> list["TranscriptParser"]:
    """Instantiate parsers for ``auto`` (all registered) or a single platform key."""
    if platform in {"auto", ""}:
        return [PARSER_REGISTRY[key]() for key in PARSER_PRIORITY]
    cls = PARSER_REGISTRY.get(platform)
    if cls is None:
        raise ValueError(f"Unsupported sidecar platform: {platform}")
    instance: TranscriptParser = cls()
    return [instance]


__all__ = [
    "ClaudeCodeTranscriptParser",
    "PARSER_PRIORITY",
    "PARSER_REGISTRY",
    "build_parsers_from_registry",
]
