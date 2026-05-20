from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from harness.usage import Usage


@dataclass(frozen=True)
class ModelPricing:
    """USD rates. Tokens priced per 1M; search priced per 1K sources."""

    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    cache_read_per_1m: float = 0.0
    cache_write_per_1m: float = 0.0
    search_per_1k_sources: float = 0.0


_DEFAULT_PATH = Path(__file__).resolve().parent / "pricing.json"


@dataclass(frozen=True)
class PricingTable:
    models: dict[str, ModelPricing]
    default_sources_per_search: int = 10

    def lookup(self, model: str) -> Optional[ModelPricing]:
        """Longest-prefix match. `claude-sonnet-4-6` matches `claude-sonnet-4`."""
        if not model:
            return None
        best_key = ""
        for key in self.models:
            if model.startswith(key) and len(key) > len(best_key):
                best_key = key
        if not best_key:
            return None
        return self.models[best_key]


def load_pricing(path: Optional[Path] = None) -> PricingTable:
    src = Path(path) if path is not None else _DEFAULT_PATH
    if not src.exists():
        return PricingTable(models={})
    raw = json.loads(src.read_text(encoding="utf-8"))
    models_raw = raw.get("models", {})
    models: dict[str, ModelPricing] = {}
    for key, entry in models_raw.items():
        models[key] = ModelPricing(
            input_per_1m=float(entry.get("input_per_1m", 0.0)),
            output_per_1m=float(entry.get("output_per_1m", 0.0)),
            cache_read_per_1m=float(entry.get("cache_read_per_1m", 0.0)),
            cache_write_per_1m=float(entry.get("cache_write_per_1m", 0.0)),
            search_per_1k_sources=float(entry.get("search_per_1k_sources", 0.0)),
        )
    return PricingTable(
        models=models,
        default_sources_per_search=int(raw.get("default_sources_per_search", 10)),
    )


def compute_cost(usage: Usage, table: PricingTable) -> Usage:
    """Attach USD costs to a Usage using the given pricing table.

    If the usage reports `server_search_calls` but `server_sources` is zero,
    we estimate sources using the table's `default_sources_per_search` so that
    Live Search doesn't show as free just because the provider didn't echo
    a source count.
    """
    pricing = table.lookup(usage.model)
    if pricing is None:
        return usage.with_costs(
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            cache_read_cost_usd=0.0,
            cache_write_cost_usd=0.0,
            search_cost_usd=0.0,
            pricing_missing=True,
        )

    sources = usage.server_sources
    if sources == 0 and usage.server_search_calls > 0:
        sources = usage.server_search_calls * table.default_sources_per_search

    return usage.with_costs(
        input_cost_usd=usage.input_tokens * pricing.input_per_1m / 1_000_000,
        output_cost_usd=usage.output_tokens * pricing.output_per_1m / 1_000_000,
        cache_read_cost_usd=usage.cache_read_tokens * pricing.cache_read_per_1m / 1_000_000,
        cache_write_cost_usd=usage.cache_write_tokens * pricing.cache_write_per_1m / 1_000_000,
        search_cost_usd=sources * pricing.search_per_1k_sources / 1_000,
        pricing_missing=False,
    )
