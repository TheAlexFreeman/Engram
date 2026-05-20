from __future__ import annotations

import json
from pathlib import Path

from harness.report import (
    aggregate,
    format_directory_summary,
    format_report,
)


def _write_trace(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_aggregate_uses_session_usage_and_counts_tools(tmp_path: Path):
    trace = tmp_path / "a.jsonl"
    _write_trace(
        trace,
        [
            {"kind": "session_start", "task": "do stuff"},
            {"kind": "usage", "turn": 0, "input_tokens": 100, "output_tokens": 50, "total_cost_usd": 0.01},
            {"kind": "tool_call", "name": "read_file"},
            {"kind": "tool_result", "name": "read_file", "is_error": False},
            {"kind": "tool_call", "name": "read_file"},
            {"kind": "tool_result", "name": "read_file", "is_error": True},
            {"kind": "tool_call", "name": "bash"},
            {"kind": "tool_result", "name": "bash", "is_error": False},
            {"kind": "usage", "turn": 1, "input_tokens": 200, "output_tokens": 75, "total_cost_usd": 0.02},
            {
                "kind": "session_usage",
                "input_tokens": 300,
                "output_tokens": 125,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "reasoning_tokens": 0,
                "server_search_calls": 0,
                "server_sources": 0,
                "total_cost_usd": 0.03,
                "pricing_missing": False,
                "missing_models": [],
            },
            {"kind": "session_end", "turns": 2},
        ],
    )
    r = aggregate(trace)
    assert r.task == "do stuff"
    assert r.turns == 2
    assert r.input_tokens == 300
    assert r.output_tokens == 125
    assert r.total_cost_usd == 0.03
    assert r.tool_counts["read_file"] == 2
    assert r.tool_counts["bash"] == 1
    assert r.tool_errors["read_file"] == 1


def test_aggregate_falls_back_to_per_turn_when_session_usage_missing(tmp_path: Path):
    trace = tmp_path / "b.jsonl"
    _write_trace(
        trace,
        [
            {"kind": "session_start", "task": "partial"},
            {"kind": "usage", "turn": 0, "input_tokens": 10, "output_tokens": 5, "total_cost_usd": 0.001},
            {"kind": "usage", "turn": 1, "input_tokens": 20, "output_tokens": 7, "total_cost_usd": 0.002},
        ],
    )
    r = aggregate(trace)
    assert r.input_tokens == 30
    assert r.output_tokens == 12
    assert r.total_cost_usd == 0.003
    assert r.turns == 2


def test_aggregate_carries_pricing_missing(tmp_path: Path):
    trace = tmp_path / "c.jsonl"
    _write_trace(
        trace,
        [
            {"kind": "session_start", "task": "mystery"},
            {
                "kind": "session_usage",
                "input_tokens": 1,
                "output_tokens": 1,
                "total_cost_usd": 0.0,
                "pricing_missing": True,
                "missing_models": ["mystery-model"],
            },
            {"kind": "session_end", "turns": 1},
        ],
    )
    r = aggregate(trace)
    assert r.pricing_missing is True
    assert "mystery-model" in r.missing_models


def test_format_report_includes_expected_lines(tmp_path: Path):
    trace = tmp_path / "d.jsonl"
    _write_trace(
        trace,
        [
            {"kind": "session_start", "task": "hi"},
            {"kind": "tool_call", "name": "bash"},
            {"kind": "tool_result", "name": "bash", "is_error": False},
            {
                "kind": "session_usage",
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_cost_usd": 0.0105,
            },
            {"kind": "session_end", "turns": 1},
        ],
    )
    out = format_report(aggregate(trace))
    assert "turns: 1" in out
    assert "in=1,000" in out
    assert "out=500" in out
    assert "$0.0105" in out
    assert "bash=1" in out


def test_format_directory_summary(tmp_path: Path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write_trace(
        a,
        [
            {
                "kind": "session_usage",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_cost_usd": 0.01,
            },
            {"kind": "session_end", "turns": 1},
        ],
    )
    _write_trace(
        b,
        [
            {
                "kind": "session_usage",
                "input_tokens": 200,
                "output_tokens": 75,
                "total_cost_usd": 0.02,
            },
            {"kind": "session_end", "turns": 2},
        ],
    )
    out = format_directory_summary([aggregate(a), aggregate(b)])
    assert "TOTAL" in out
    assert "300" in out
    assert "$   0.0300" in out or "$0.0300" in out
