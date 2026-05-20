from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class TraceReport:
    path: Path
    task: str = ""
    turns: int = 0
    end_reason: str | None = None
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
    missing_models: set[str] = field(default_factory=set)
    tool_counts: Counter = field(default_factory=Counter)
    tool_errors: Counter = field(default_factory=Counter)


def _iter_events(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def aggregate(path: Path) -> TraceReport:
    """Summarize a single JSONL trace. Prefers `session_usage` totals when
    present; falls back to summing per-turn `usage` events so partial traces
    (e.g. crashed runs) still report something."""
    report = TraceReport(path=path)
    turn_usages: list[dict] = []
    session_usage: dict | None = None

    for event in _iter_events(path):
        kind = event.get("kind")
        if kind == "session_start":
            report.task = str(event.get("task", ""))
        elif kind == "session_end":
            report.turns = int(event.get("turns", report.turns) or 0)
            report.end_reason = event.get("reason")
        elif kind == "usage":
            turn_usages.append(event)
        elif kind == "session_usage":
            session_usage = event
        elif kind == "tool_call":
            name = str(event.get("name", ""))
            if name:
                report.tool_counts[name] += 1
        elif kind == "tool_result":
            if event.get("is_error"):
                name = str(event.get("name", ""))
                if name:
                    report.tool_errors[name] += 1

    source = session_usage if session_usage is not None else _sum_usages(turn_usages)
    if source:
        report.input_tokens = int(source.get("input_tokens", 0) or 0)
        report.output_tokens = int(source.get("output_tokens", 0) or 0)
        report.cache_read_tokens = int(source.get("cache_read_tokens", 0) or 0)
        report.cache_write_tokens = int(source.get("cache_write_tokens", 0) or 0)
        report.reasoning_tokens = int(source.get("reasoning_tokens", 0) or 0)
        report.server_search_calls = int(source.get("server_search_calls", 0) or 0)
        report.server_sources = int(source.get("server_sources", 0) or 0)
        report.input_cost_usd = float(source.get("input_cost_usd", 0.0) or 0.0)
        report.output_cost_usd = float(source.get("output_cost_usd", 0.0) or 0.0)
        report.cache_read_cost_usd = float(source.get("cache_read_cost_usd", 0.0) or 0.0)
        report.cache_write_cost_usd = float(source.get("cache_write_cost_usd", 0.0) or 0.0)
        report.search_cost_usd = float(source.get("search_cost_usd", 0.0) or 0.0)
        report.total_cost_usd = float(source.get("total_cost_usd", 0.0) or 0.0)
        report.pricing_missing = bool(source.get("pricing_missing", False))
        report.missing_models = set(source.get("missing_models", []) or [])

    if report.turns == 0 and turn_usages:
        report.turns = len(turn_usages)

    return report


_SUM_INT_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "server_search_calls",
    "server_sources",
)
_SUM_FLOAT_KEYS = (
    "input_cost_usd",
    "output_cost_usd",
    "cache_read_cost_usd",
    "cache_write_cost_usd",
    "search_cost_usd",
    "total_cost_usd",
)


def _sum_usages(events: list[dict]) -> dict:
    total: dict = {k: 0 for k in _SUM_INT_KEYS}
    for k in _SUM_FLOAT_KEYS:
        total[k] = 0.0
    total["pricing_missing"] = False
    missing: set[str] = set()
    for e in events:
        for k in _SUM_INT_KEYS:
            total[k] += int(e.get(k, 0) or 0)
        for k in _SUM_FLOAT_KEYS:
            total[k] += float(e.get(k, 0.0) or 0.0)
        if e.get("pricing_missing"):
            total["pricing_missing"] = True
        missing.update(e.get("missing_models", []) or [])
    total["missing_models"] = sorted(missing)
    return total


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def format_report(report: TraceReport) -> str:
    lines: list[str] = []
    lines.append(f"trace: {report.path}")
    if report.task:
        lines.append(f"task:  {_truncate(report.task, 100)}")
    end = f"turns: {report.turns}"
    if report.end_reason:
        end += f" ({report.end_reason})"
    lines.append(end)
    lines.append(
        f"tokens: in={report.input_tokens:,} out={report.output_tokens:,} "
        f"cache_r={report.cache_read_tokens:,} cache_w={report.cache_write_tokens:,} "
        f"reason={report.reasoning_tokens:,}"
    )
    if report.server_search_calls or report.server_sources:
        lines.append(
            f"search: calls={report.server_search_calls} sources={report.server_sources}"
        )
    lines.append(
        f"cost:  ${report.total_cost_usd:.4f} total  "
        f"(in ${report.input_cost_usd:.4f} / out ${report.output_cost_usd:.4f} / "
        f"cache ${report.cache_read_cost_usd + report.cache_write_cost_usd:.4f} / "
        f"search ${report.search_cost_usd:.4f})"
    )
    if report.pricing_missing:
        models = ", ".join(sorted(report.missing_models)) or "(unknown)"
        lines.append(f"[warning] no pricing for model(s): {models}")
    if report.tool_counts:
        top = report.tool_counts.most_common(10)
        tools_line = "tools: " + ", ".join(
            f"{name}={count}" for name, count in top
        )
        lines.append(tools_line)
    if report.tool_errors:
        err_line = "errors: " + ", ".join(
            f"{name}={count}" for name, count in report.tool_errors.most_common()
        )
        lines.append(err_line)
    return "\n".join(lines)


def _collect_paths(target: Path) -> list[Path]:
    if target.is_dir():
        return sorted(target.glob("*.jsonl"))
    return [target]


def format_directory_summary(reports: list[TraceReport]) -> str:
    if not reports:
        return "(no traces found)"
    header = f"{'trace':<42} {'turns':>5} {'in':>10} {'out':>10} {'cost':>10}"
    rows = [header, "-" * len(header)]
    total_in = total_out = 0
    total_cost = 0.0
    any_missing = False
    missing_models: set[str] = set()
    for r in reports:
        rows.append(
            f"{_truncate(r.path.name, 42):<42} "
            f"{r.turns:>5} {r.input_tokens:>10,} {r.output_tokens:>10,} "
            f"${r.total_cost_usd:>9.4f}"
        )
        total_in += r.input_tokens
        total_out += r.output_tokens
        total_cost += r.total_cost_usd
        if r.pricing_missing:
            any_missing = True
            missing_models.update(r.missing_models)
    rows.append("-" * len(header))
    rows.append(
        f"{'TOTAL':<42} {'':>5} {total_in:>10,} {total_out:>10,} ${total_cost:>9.4f}"
    )
    if any_missing:
        models = ", ".join(sorted(missing_models)) or "(unknown)"
        rows.append(f"[warning] no pricing for model(s): {models}")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harness-report",
        description="Summarize tokens, cost, and tool usage from harness trace JSONL files.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a .jsonl trace file, or a directory containing trace files.",
    )
    args = parser.parse_args(argv)

    target: Path = args.path
    if not target.exists():
        print(f"error: {target} does not exist", file=sys.stderr)
        return 2

    paths = _collect_paths(target)
    reports = [aggregate(p) for p in paths]

    if target.is_dir():
        print(format_directory_summary(reports))
    else:
        for r in reports:
            print(format_report(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
