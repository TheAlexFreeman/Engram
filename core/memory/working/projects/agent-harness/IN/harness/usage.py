from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class Usage:
    """Per-turn or aggregated token + cost accounting.

    Token counts are integers; cost fields are USD floats. Provider-agnostic:
    Anthropic fills cache_read/write and leaves reasoning/search at 0; xAI fills
    reasoning_tokens and server_search_calls/server_sources and leaves cache at 0.
    """

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    server_search_calls: int = 0
    server_sources: int = 0

    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    cache_read_cost_usd: float = 0.0
    cache_write_cost_usd: float = 0.0
    search_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    pricing_missing: bool = False
    missing_models: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def zero() -> "Usage":
        return Usage()

    def __add__(self, other: "Usage") -> "Usage":
        if not isinstance(other, Usage):
            return NotImplemented
        missing = tuple(sorted(set(self.missing_models) | set(other.missing_models)))
        return Usage(
            model=self.model if self.model == other.model else "",
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            server_search_calls=self.server_search_calls + other.server_search_calls,
            server_sources=self.server_sources + other.server_sources,
            input_cost_usd=self.input_cost_usd + other.input_cost_usd,
            output_cost_usd=self.output_cost_usd + other.output_cost_usd,
            cache_read_cost_usd=self.cache_read_cost_usd + other.cache_read_cost_usd,
            cache_write_cost_usd=self.cache_write_cost_usd + other.cache_write_cost_usd,
            search_cost_usd=self.search_cost_usd + other.search_cost_usd,
            total_cost_usd=self.total_cost_usd + other.total_cost_usd,
            pricing_missing=self.pricing_missing or other.pricing_missing,
            missing_models=missing,
        )

    def with_costs(
        self,
        *,
        input_cost_usd: float,
        output_cost_usd: float,
        cache_read_cost_usd: float,
        cache_write_cost_usd: float,
        search_cost_usd: float,
        pricing_missing: bool,
    ) -> "Usage":
        total = (
            input_cost_usd
            + output_cost_usd
            + cache_read_cost_usd
            + cache_write_cost_usd
            + search_cost_usd
        )
        missing_models = (self.model,) if pricing_missing and self.model else ()
        return replace(
            self,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            cache_read_cost_usd=cache_read_cost_usd,
            cache_write_cost_usd=cache_write_cost_usd,
            search_cost_usd=search_cost_usd,
            total_cost_usd=total,
            pricing_missing=pricing_missing,
            missing_models=missing_models,
        )

    def as_trace_dict(self) -> dict[str, Any]:
        """Compact dict for trace events. Zero-valued fields are kept so
        downstream consumers can rely on a stable schema."""
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "server_search_calls": self.server_search_calls,
            "server_sources": self.server_sources,
            "input_cost_usd": round(self.input_cost_usd, 6),
            "output_cost_usd": round(self.output_cost_usd, 6),
            "cache_read_cost_usd": round(self.cache_read_cost_usd, 6),
            "cache_write_cost_usd": round(self.cache_write_cost_usd, 6),
            "search_cost_usd": round(self.search_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "pricing_missing": self.pricing_missing,
            "missing_models": list(self.missing_models),
        }
