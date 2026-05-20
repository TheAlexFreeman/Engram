from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.pricing import ModelPricing, PricingTable, compute_cost, load_pricing
from harness.usage import Usage


def test_usage_addition_sums_all_fields():
    a = Usage(
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=10,
        cache_write_tokens=5,
        reasoning_tokens=20,
        server_search_calls=1,
        server_sources=8,
        input_cost_usd=0.1,
        output_cost_usd=0.2,
        total_cost_usd=0.3,
    )
    b = Usage(
        model="claude-sonnet-4-6",
        input_tokens=1,
        output_tokens=2,
        cache_read_tokens=3,
        cache_write_tokens=4,
        reasoning_tokens=5,
        server_search_calls=2,
        server_sources=3,
        input_cost_usd=0.01,
        output_cost_usd=0.02,
        total_cost_usd=0.03,
    )
    c = a + b
    assert c.input_tokens == 101
    assert c.output_tokens == 52
    assert c.cache_read_tokens == 13
    assert c.cache_write_tokens == 9
    assert c.reasoning_tokens == 25
    assert c.server_search_calls == 3
    assert c.server_sources == 11
    assert c.total_cost_usd == pytest.approx(0.33)
    assert c.model == "claude-sonnet-4-6"


def test_usage_addition_flags_missing_across_runs():
    a = Usage(model="claude-sonnet-4-6", input_tokens=10)
    b = Usage(model="unknown-foo", input_tokens=5, pricing_missing=True, missing_models=("unknown-foo",))
    c = a + b
    assert c.pricing_missing is True
    assert "unknown-foo" in c.missing_models


def test_as_trace_dict_has_stable_keys():
    u = Usage(model="grok-4", input_tokens=5, output_tokens=3)
    d = u.as_trace_dict()
    for k in (
        "model",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "server_search_calls",
        "server_sources",
        "input_cost_usd",
        "output_cost_usd",
        "cache_read_cost_usd",
        "cache_write_cost_usd",
        "search_cost_usd",
        "total_cost_usd",
        "pricing_missing",
        "missing_models",
    ):
        assert k in d


def test_pricing_longest_prefix_wins():
    table = PricingTable(
        models={
            "claude-sonnet-4": ModelPricing(input_per_1m=3.0, output_per_1m=15.0),
            "claude": ModelPricing(input_per_1m=999.0, output_per_1m=999.0),
        }
    )
    p = table.lookup("claude-sonnet-4-6")
    assert p is not None
    assert p.input_per_1m == 3.0


def test_pricing_unknown_returns_none():
    table = PricingTable(models={"claude-sonnet-4": ModelPricing(input_per_1m=1.0)})
    assert table.lookup("gpt-5") is None


def test_compute_cost_arithmetic():
    table = PricingTable(
        models={
            "claude-sonnet-4": ModelPricing(
                input_per_1m=3.0,
                output_per_1m=15.0,
                cache_read_per_1m=0.3,
                cache_write_per_1m=3.75,
            )
        }
    )
    u = Usage(
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
    )
    priced = compute_cost(u, table)
    assert priced.input_cost_usd == pytest.approx(3.0)
    assert priced.output_cost_usd == pytest.approx(15.0)
    assert priced.cache_read_cost_usd == pytest.approx(0.3)
    assert priced.cache_write_cost_usd == pytest.approx(3.75)
    assert priced.total_cost_usd == pytest.approx(3.0 + 15.0 + 0.3 + 3.75)
    assert priced.pricing_missing is False


def test_compute_cost_grok_search_by_sources():
    table = PricingTable(
        models={"grok-4": ModelPricing(search_per_1k_sources=25.0)},
        default_sources_per_search=10,
    )
    u = Usage(model="grok-4", server_sources=40)
    priced = compute_cost(u, table)
    assert priced.search_cost_usd == pytest.approx(1.0)


def test_compute_cost_grok_search_falls_back_to_call_count():
    table = PricingTable(
        models={"grok-4": ModelPricing(search_per_1k_sources=25.0)},
        default_sources_per_search=10,
    )
    u = Usage(model="grok-4", server_search_calls=4, server_sources=0)
    priced = compute_cost(u, table)
    assert priced.search_cost_usd == pytest.approx(1.0)


def test_compute_cost_unknown_model_sets_missing_flag():
    table = PricingTable(models={"claude-sonnet-4": ModelPricing(input_per_1m=3.0)})
    u = Usage(model="mystery-model", input_tokens=500)
    priced = compute_cost(u, table)
    assert priced.pricing_missing is True
    assert priced.total_cost_usd == 0.0
    assert "mystery-model" in priced.missing_models


def test_load_pricing_from_file(tmp_path: Path):
    p = tmp_path / "pricing.json"
    p.write_text(
        json.dumps(
            {
                "default_sources_per_search": 5,
                "models": {
                    "foo": {"input_per_1m": 2.0, "output_per_1m": 4.0},
                },
            }
        ),
        encoding="utf-8",
    )
    table = load_pricing(p)
    assert table.default_sources_per_search == 5
    assert table.lookup("foo-bar").input_per_1m == 2.0


def test_load_pricing_default_ships_grok_and_claude():
    table = load_pricing()
    assert table.lookup("claude-sonnet-4-6") is not None
    assert table.lookup("grok-4-20-0309") is not None
