"""Tests for freshness scoring and freshness-weighted memory_search."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_memory_mcp_module():
    spec = importlib.util.spec_from_file_location(
        "memory_mcp",
        REPO_ROOT / "core" / "tools" / "memory_mcp.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"memory_mcp dependencies unavailable: {exc.name}")
    return module


# ---------------------------------------------------------------------------
# Unit tests for the freshness utility (no MCP dependency)
# ---------------------------------------------------------------------------
class TestFreshnessScore(unittest.TestCase):
    """Tests for core.tools.agent_memory_mcp.freshness."""

    def setUp(self) -> None:
        from core.tools.agent_memory_mcp.freshness import (
            DEFAULT_HALF_LIFE_DAYS,
            effective_date,
            freshness_score,
            parse_date,
        )

        self.freshness_score = freshness_score
        self.effective_date = effective_date
        self.parse_date = parse_date
        self.half_life = DEFAULT_HALF_LIFE_DAYS

    # -- parse_date ---------------------------------------------------------

    def test_parse_date_string(self) -> None:
        self.assertEqual(self.parse_date("2026-03-27"), date(2026, 3, 27))

    def test_parse_date_date_object(self) -> None:
        d = date(2026, 1, 1)
        self.assertIs(self.parse_date(d), d)

    def test_parse_date_none(self) -> None:
        self.assertIsNone(self.parse_date(None))

    def test_parse_date_empty_string(self) -> None:
        self.assertIsNone(self.parse_date(""))

    def test_parse_date_invalid(self) -> None:
        self.assertIsNone(self.parse_date("not-a-date"))

    # -- effective_date -----------------------------------------------------

    def test_effective_date_prefers_last_verified(self) -> None:
        fm = {"last_verified": "2026-03-20", "created": "2026-01-01"}
        self.assertEqual(self.effective_date(fm), date(2026, 3, 20))

    def test_effective_date_falls_back_to_created(self) -> None:
        fm = {"created": "2026-01-15"}
        self.assertEqual(self.effective_date(fm), date(2026, 1, 15))

    def test_effective_date_none_when_empty(self) -> None:
        self.assertIsNone(self.effective_date({}))

    # -- freshness_score ----------------------------------------------------

    def test_today_scores_one(self) -> None:
        today = date(2026, 3, 27)
        self.assertAlmostEqual(self.freshness_score(today, today=today), 1.0)

    def test_half_life_scores_half(self) -> None:
        today = date(2026, 3, 27)
        past = today - timedelta(days=self.half_life)
        self.assertAlmostEqual(self.freshness_score(past, today=today), 0.5, places=5)

    def test_double_half_life_scores_quarter(self) -> None:
        today = date(2026, 3, 27)
        past = today - timedelta(days=self.half_life * 2)
        self.assertAlmostEqual(self.freshness_score(past, today=today), 0.25, places=5)

    def test_none_scores_zero(self) -> None:
        self.assertAlmostEqual(self.freshness_score(None), 0.0)

    def test_future_date_scores_one(self) -> None:
        today = date(2026, 3, 27)
        future = today + timedelta(days=30)
        self.assertAlmostEqual(self.freshness_score(future, today=today), 1.0)

    def test_custom_half_life(self) -> None:
        today = date(2026, 3, 27)
        past = today - timedelta(days=90)
        # With 90-day half-life, 90 days ago → 0.5
        self.assertAlmostEqual(
            self.freshness_score(past, today=today, half_life_days=90),
            0.5,
            places=5,
        )


# ---------------------------------------------------------------------------
# Integration tests for memory_search freshness_weight parameter
# ---------------------------------------------------------------------------
class TestSearchFreshnessWeight(unittest.TestCase):
    """Tests for the freshness_weight parameter on memory_search."""

    module = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_memory_mcp_module()

    def _search(self, **kwargs) -> str:
        return asyncio.run(self.module.memory_search(**kwargs))

    def test_default_weight_zero_returns_results(self) -> None:
        """With default freshness_weight=0, search still returns results."""
        output = self._search(query="trust", path="memory/knowledge")
        # Should find matches in some knowledge files
        self.assertNotIn("No matches", output)

    def test_freshness_weight_zero_no_freshness_annotation(self) -> None:
        """With freshness_weight=0, output should not contain freshness scores."""
        output = self._search(query="trust", path="memory/knowledge")
        self.assertNotIn("freshness:", output)

    def test_freshness_weight_positive_adds_annotation(self) -> None:
        """With freshness_weight > 0, output should contain freshness annotations."""
        output = self._search(
            query="trust",
            path="memory/knowledge",
            freshness_weight=0.5,
        )
        if "No matches" not in output:
            self.assertIn("freshness:", output)

    def test_freshness_weight_clamped_above_one(self) -> None:
        """Values > 1.0 are clamped to 1.0 without error."""
        output = self._search(
            query="trust",
            path="memory/knowledge",
            freshness_weight=2.0,
        )
        # Should not raise; just clamp
        self.assertIsInstance(output, str)

    def test_freshness_weight_clamped_below_zero(self) -> None:
        """Values < 0.0 are clamped to 0.0 without error."""
        output = self._search(
            query="trust",
            path="memory/knowledge",
            freshness_weight=-1.0,
        )
        self.assertIsInstance(output, str)
        # Clamped to 0 → no freshness annotation
        self.assertNotIn("freshness:", output)


if __name__ == "__main__":
    unittest.main()
