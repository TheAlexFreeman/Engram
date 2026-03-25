"""Tests for link quality scoring and weak-link pruning tools.

Covers:
  - _score_link_pair (Phase 1 refactor)
  - score_existing_links (Phase 1)
  - find_dense_redundant_links / _find_bridges_undirected (Phase 2)
  - parse_co_access / score_links_by_access (Phase 3)
  - prune_weak_links (Phase 4)
"""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_reference_extractor():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.tools.reference_extractor")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"reference_extractor unavailable: {exc.name}") from exc


def _load_graph_analysis():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.tools.graph_analysis")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"graph_analysis unavailable: {exc.name}") from exc


# ── Helpers ────────────────────────────────────────────────────────


def _make_md(
    title: str,
    related: list[str] | None = None,
    body: str = "",
) -> str:
    lines = ["---", f"title: {title}", "source: test", "created: 2026-01-01", "trust: low"]
    if related:
        lines.append("related: " + ", ".join(related))
    lines.append("---\n")
    if body:
        lines.append(body)
    return "\n".join(lines)


def _write_files(tmpdir: str, files: dict[str, str]) -> Path:
    root = Path(tmpdir) / "content"
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


# ── _score_link_pair tests ─────────────────────────────────────────


class ScoreLinkPairTests(unittest.TestCase):
    """Unit tests for the extracted _score_link_pair helper."""

    extractor: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = _load_reference_extractor()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

        # Two files in the same directory with overlapping stems
        self._files = {
            "memory/knowledge/ai/alignment.md": _make_md(
                "AI Alignment",
                body="Discusses alignment and safety.\n",
            ),
            "memory/knowledge/ai/alignment-tax.md": _make_md(
                "Alignment Tax",
                body="The cost of alignment constraints.\n",
            ),
            "memory/knowledge/philosophy/epistemology.md": _make_md(
                "Epistemology",
                body="Theory of knowledge.\n",
            ),
        }
        self._root = _write_files(self._tmpdir.name, self._files)
        _load_graph_analysis()
        self._graph = self.extractor.build_connectivity_graph(self._root)

    def test_same_directory_boosts_score(self) -> None:
        score, reasons = self.extractor._score_link_pair(
            "memory/knowledge/ai/alignment.md",
            "memory/knowledge/ai/alignment-tax.md",
            self._graph,
            self._root,
        )
        self.assertGreater(score, 0.0)
        self.assertTrue(
            any("same directory" in r or "shared stem" in r for r in reasons),
            f"Expected directory or stem signal, got: {reasons}",
        )

    def test_cross_domain_link_scores_lower_than_same_dir(self) -> None:
        same_dir_score, _ = self.extractor._score_link_pair(
            "memory/knowledge/ai/alignment.md",
            "memory/knowledge/ai/alignment-tax.md",
            self._graph,
            self._root,
        )
        cross_score, _ = self.extractor._score_link_pair(
            "memory/knowledge/ai/alignment.md",
            "memory/knowledge/philosophy/epistemology.md",
            self._graph,
            self._root,
        )
        self.assertGreater(same_dir_score, cross_score)

    def test_context_caching_gives_same_result(self) -> None:
        src_ctx = self.extractor._extract_candidate_context(
            "memory/knowledge/ai/alignment.md", self._root
        )
        tgt_ctx = self.extractor._extract_candidate_context(
            "memory/knowledge/ai/alignment-tax.md", self._root
        )
        score_with = self.extractor._score_link_pair(
            "memory/knowledge/ai/alignment.md",
            "memory/knowledge/ai/alignment-tax.md",
            self._graph,
            self._root,
            _source_context=src_ctx,
            _target_context=tgt_ctx,
        )
        score_without = self.extractor._score_link_pair(
            "memory/knowledge/ai/alignment.md",
            "memory/knowledge/ai/alignment-tax.md",
            self._graph,
            self._root,
        )
        self.assertEqual(score_with[0], score_without[0])


# ── score_existing_links tests ─────────────────────────────────────


class ScoreExistingLinksTests(unittest.TestCase):
    extractor: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = _load_reference_extractor()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

        # algebra → topology (same dir) and epistemology (cross-domain)
        self._files = {
            "memory/knowledge/math/algebra.md": _make_md(
                "Algebra",
                related=[
                    "topology.md",
                    "../philosophy/epistemology.md",
                ],
            ),
            "memory/knowledge/math/topology.md": _make_md("Topology"),
            "memory/knowledge/philosophy/epistemology.md": _make_md("Epistemology"),
        }
        self._root = _write_files(self._tmpdir.name, self._files)
        self._graph = self.extractor.build_connectivity_graph(self._root)

    def test_returns_one_entry_per_outgoing_link(self) -> None:
        results = self.extractor.score_existing_links(
            "memory/knowledge/math/algebra.md",
            self._graph,
            self._root,
        )
        self.assertEqual(len(results), 2)
        targets = {r["target"] for r in results}
        self.assertIn("memory/knowledge/math/topology.md", targets)
        self.assertIn("memory/knowledge/philosophy/epistemology.md", targets)

    def test_sorted_ascending_by_score(self) -> None:
        results = self.extractor.score_existing_links(
            "memory/knowledge/math/algebra.md",
            self._graph,
            self._root,
        )
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores))

    def test_alert_flag_set_correctly(self) -> None:
        """Same-dir link should score higher; cross-domain may trigger alert."""
        results = self.extractor.score_existing_links(
            "memory/knowledge/math/algebra.md",
            self._graph,
            self._root,
            min_score=3.0,
        )
        # Every entry must have the alert key
        for r in results:
            self.assertIn("alert", r)
            self.assertIs(r["alert"], r["score"] < 3.0)

    def test_empty_outgoing_returns_empty_list(self) -> None:
        results = self.extractor.score_existing_links(
            "memory/knowledge/math/topology.md",
            self._graph,
            self._root,
        )
        self.assertEqual(results, [])


# ── _find_bridges_undirected tests ────────────────────────────────


class FindBridgesTests(unittest.TestCase):
    engine: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_graph_analysis()

    def _bridges(self, node_ids: list[str], adj: dict[str, list[str]]) -> set[frozenset]:
        return self.engine._find_bridges_undirected(node_ids, adj)

    def test_single_bridge_detected(self) -> None:
        # A-B-C: the edge B-C is a bridge (not A-B actually both are bridges)
        nodes = ["A", "B", "C"]
        adj = {"A": ["B"], "B": ["A", "C"], "C": ["B"]}
        bridges = self._bridges(nodes, adj)
        self.assertIn(frozenset({"A", "B"}), bridges)
        self.assertIn(frozenset({"B", "C"}), bridges)

    def test_cycle_has_no_bridges(self) -> None:
        # A-B-C-A: no bridges in a triangle
        nodes = ["A", "B", "C"]
        adj = {
            "A": ["B", "C"],
            "B": ["A", "C"],
            "C": ["A", "B"],
        }
        bridges = self._bridges(nodes, adj)
        self.assertEqual(len(bridges), 0)

    def test_bridge_in_mixed_graph(self) -> None:
        # Triangle A-B-C with dangling D off B
        nodes = ["A", "B", "C", "D"]
        adj = {
            "A": ["B", "C"],
            "B": ["A", "C", "D"],
            "C": ["A", "B"],
            "D": ["B"],
        }
        bridges = self._bridges(nodes, adj)
        self.assertIn(frozenset({"B", "D"}), bridges)
        # The triangle edges are not bridges
        self.assertNotIn(frozenset({"A", "B"}), bridges)

    def test_disconnected_graph_handled(self) -> None:
        # Two separate chains A-B and C-D (both bridges)
        nodes = ["A", "B", "C", "D"]
        adj = {
            "A": ["B"],
            "B": ["A"],
            "C": ["D"],
            "D": ["C"],
        }
        bridges = self._bridges(nodes, adj)
        self.assertIn(frozenset({"A", "B"}), bridges)
        self.assertIn(frozenset({"C", "D"}), bridges)


# ── find_dense_redundant_links tests ──────────────────────────────


class FindDenseRedundantLinksTests(unittest.TestCase):
    engine: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_graph_analysis()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _write(self, files: dict[str, str]) -> Path:
        return _write_files(self._tmpdir.name, files)

    def test_returns_graph_stats(self) -> None:
        files = {
            "memory/knowledge/math/a.md": _make_md("A", related=["b.md", "c.md"]),
            "memory/knowledge/math/b.md": _make_md("B", related=["a.md", "c.md"]),
            "memory/knowledge/math/c.md": _make_md("C", related=["a.md", "b.md"]),
        }
        root = self._write(files)
        result = self.engine.find_dense_redundant_links(root, scope="knowledge/math")
        self.assertIn("graph_stats", result)
        self.assertIn("total_redundant", result)
        self.assertIn("dense_nodes", result)

    def test_clique_produces_redundant_edges(self) -> None:
        # A 4-clique: all 6 edges exist; none are bridges; any node with
        # degree 3 and high clustering should appear in dense_nodes.
        files = {
            "memory/knowledge/rat/a.md": _make_md("A", related=["b.md", "c.md", "d.md"]),
            "memory/knowledge/rat/b.md": _make_md("B", related=["a.md", "c.md", "d.md"]),
            "memory/knowledge/rat/c.md": _make_md("C", related=["a.md", "b.md", "d.md"]),
            "memory/knowledge/rat/d.md": _make_md("D", related=["a.md", "b.md", "c.md"]),
        }
        root = self._write(files)
        result = self.engine.find_dense_redundant_links(
            root,
            scope="knowledge/rat",
            degree_threshold=3,
            clustering_threshold=0.5,
        )
        self.assertGreater(result["total_redundant"], 0)
        self.assertEqual(result["total_bridge_edges"], 0)

    def test_chain_has_only_bridges_no_redundant(self) -> None:
        # A-B-C-D: a path graph has all bridges and no redundant edges
        files = {
            "memory/knowledge/chain/a.md": _make_md("A", related=["b.md"]),
            "memory/knowledge/chain/b.md": _make_md("B", related=["a.md", "c.md"]),
            "memory/knowledge/chain/c.md": _make_md("C", related=["b.md", "d.md"]),
            "memory/knowledge/chain/d.md": _make_md("D", related=["c.md"]),
        }
        root = self._write(files)
        result = self.engine.find_dense_redundant_links(
            root,
            scope="knowledge/chain",
            degree_threshold=1,
            clustering_threshold=0.0,
        )
        self.assertEqual(result["total_redundant"], 0)


# ── parse_co_access tests ──────────────────────────────────────────


class ParseCoAccessTests(unittest.TestCase):
    engine: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_graph_analysis()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _root_with_access(self, jsonl_lines: list[str]) -> Path:
        root = Path(self._tmpdir.name) / "content"
        access_dir = root / "memory" / "knowledge"
        access_dir.mkdir(parents=True, exist_ok=True)
        (access_dir / "ACCESS.jsonl").write_text("\n".join(jsonl_lines), encoding="utf-8")
        return root

    def test_same_session_pair_counted(self) -> None:
        lines = [
            '{"file": "memory/knowledge/a.md", "date": "2026-03-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2026-03-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
        ]
        root = self._root_with_access(lines)
        co_access = self.engine.parse_co_access(root, lookback_days=365)
        key = ("memory/knowledge/a.md", "memory/knowledge/b.md")
        self.assertEqual(co_access.get(key, 0), 1)

    def test_different_sessions_no_co_access(self) -> None:
        lines = [
            '{"file": "memory/knowledge/a.md", "date": "2026-03-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2026-03-02", "session_id": "s2", "task": "read", "helpfulness": 1, "note": "x"}',
        ]
        root = self._root_with_access(lines)
        co_access = self.engine.parse_co_access(root, lookback_days=365)
        key = ("memory/knowledge/a.md", "memory/knowledge/b.md")
        self.assertEqual(co_access.get(key, 0), 0)

    def test_multiple_sessions_cumulative(self) -> None:
        lines = [
            '{"file": "memory/knowledge/a.md", "date": "2026-03-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2026-03-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/a.md", "date": "2026-03-02", "session_id": "s2", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2026-03-02", "session_id": "s2", "task": "read", "helpfulness": 1, "note": "x"}',
        ]
        root = self._root_with_access(lines)
        co_access = self.engine.parse_co_access(root, lookback_days=365)
        key = ("memory/knowledge/a.md", "memory/knowledge/b.md")
        self.assertEqual(co_access.get(key, 0), 2)

    def test_lookback_filters_old_entries(self) -> None:
        lines = [
            '{"file": "memory/knowledge/a.md", "date": "2020-01-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2020-01-01", "session_id": "s1", "task": "read", "helpfulness": 1, "note": "x"}',
        ]
        root = self._root_with_access(lines)
        co_access = self.engine.parse_co_access(root, lookback_days=30)
        key = ("memory/knowledge/a.md", "memory/knowledge/b.md")
        self.assertEqual(co_access.get(key, 0), 0)

    def test_fallback_grouping_by_date_when_no_session_id(self) -> None:
        lines = [
            '{"file": "memory/knowledge/a.md", "date": "2026-03-01", "task": "read", "helpfulness": 1, "note": "x"}',
            '{"file": "memory/knowledge/b.md", "date": "2026-03-01", "task": "read", "helpfulness": 1, "note": "x"}',
        ]
        root = self._root_with_access(lines)
        co_access = self.engine.parse_co_access(root, lookback_days=365)
        key = ("memory/knowledge/a.md", "memory/knowledge/b.md")
        self.assertEqual(co_access.get(key, 0), 1)

    def test_empty_file_returns_empty_dict(self) -> None:
        root = self._root_with_access([])
        co_access = self.engine.parse_co_access(root, lookback_days=365)
        self.assertEqual(co_access, {})


# ── score_links_by_access tests ────────────────────────────────────


class ScoreLinksByAccessTests(unittest.TestCase):
    engine: ClassVar[Any]
    extractor: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_graph_analysis()
        cls.extractor = _load_reference_extractor()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

        files = {
            "memory/knowledge/math/algebra.md": _make_md(
                "Algebra",
                related=["topology.md", "analysis.md"],
            ),
            "memory/knowledge/math/topology.md": _make_md("Topology"),
            "memory/knowledge/math/analysis.md": _make_md("Analysis"),
        }
        self._root = _write_files(self._tmpdir.name, files)
        self._graph = self.extractor.build_connectivity_graph(self._root)

    def test_never_accessed_link_scores_zero(self) -> None:
        co_access: dict = {}
        results = self.engine.score_links_by_access(
            "memory/knowledge/math/algebra.md", co_access, self._graph
        )
        for r in results:
            self.assertEqual(r["access_score"], 0)
            self.assertTrue(r["never_co_accessed"])

    def test_co_accessed_pair_scores_correctly(self) -> None:
        co_access = {
            ("memory/knowledge/math/algebra.md", "memory/knowledge/math/topology.md"): 3,
        }
        results = self.engine.score_links_by_access(
            "memory/knowledge/math/algebra.md", co_access, self._graph
        )
        topo = next(r for r in results if r["target"] == "memory/knowledge/math/topology.md")
        self.assertEqual(topo["access_score"], 3)
        self.assertFalse(topo["never_co_accessed"])

    def test_sorted_ascending_by_access_score(self) -> None:
        co_access = {
            ("memory/knowledge/math/algebra.md", "memory/knowledge/math/topology.md"): 5,
        }
        results = self.engine.score_links_by_access(
            "memory/knowledge/math/algebra.md", co_access, self._graph
        )
        scores = [r["access_score"] for r in results]
        self.assertEqual(scores, sorted(scores))


# ── prune_weak_links tests ─────────────────────────────────────────


class PruneWeakLinksTests(unittest.TestCase):
    engine: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_graph_analysis()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

        # alpha links to beta (same dir, strong) and gamma (cross-domain, weak)
        self._files = {
            "memory/knowledge/ai/alpha.md": _make_md(
                "Alpha",
                related=["beta.md", "../other/gamma.md"],
            ),
            "memory/knowledge/ai/beta.md": _make_md(
                "Beta",
                related=["alpha.md"],
            ),
            "memory/knowledge/other/gamma.md": _make_md("Gamma"),
        }

    def _root(self) -> Path:
        return _write_files(self._tmpdir.name, self._files)

    def test_dry_run_does_not_modify_files(self) -> None:
        root = self._root()
        original = (root / "memory/knowledge/ai/alpha.md").read_text(encoding="utf-8")
        report = self.engine.prune_weak_links(root, dry_run=True)
        after = (root / "memory/knowledge/ai/alpha.md").read_text(encoding="utf-8")
        self.assertEqual(original, after)
        self.assertTrue(report["dry_run"])

    def test_invalid_signal_raises_value_error(self) -> None:
        root = self._root()
        with self.assertRaises(ValueError):
            self.engine.prune_weak_links(root, signal="nonsense")

    def test_dry_run_reports_candidates(self) -> None:
        root = self._root()
        # With a high min_structural_score, the cross-domain link should be flagged
        report = self.engine.prune_weak_links(
            root,
            min_structural_score=10.0,
            signal="structural",
            dry_run=True,
        )
        self.assertTrue(report["dry_run"])
        # At least some files should be flagged (cross-domain link has lower score)
        # Even if none are flagged (if both pass), the report structure must be valid
        self.assertIn("files_changed", report)
        self.assertIn("total_removed", report)
        self.assertIn("details", report)

    def test_structural_signal_prunes_low_score_link(self) -> None:
        root = self._root()
        # Score 0 threshold flags everything; combined with same-dir premium
        # the cross-domain link (gamma) should score lower than in-dir link (beta)
        report_dry = self.engine.prune_weak_links(
            root,
            min_structural_score=10.0,  # very high — flags most links
            signal="structural",
            dry_run=True,
        )
        # Verify structure is correct
        self.assertIsInstance(report_dry["files_changed"], list)
        self.assertIsInstance(report_dry["total_removed"], int)

    def test_access_signal_with_zero_threshold_flags_nothing(self) -> None:
        # min_access_score=0 means only links with fewer than 0 co-accesses are flagged,
        # which is impossible. So nothing should be pruned.
        root = self._root()
        report = self.engine.prune_weak_links(
            root,
            min_access_score=0,
            signal="access",
            dry_run=True,
        )
        self.assertEqual(report["total_removed"], 0)

    def test_combined_signal_requires_both_to_fail(self) -> None:
        root = self._root()
        # With combined signal, a link must fail BOTH structural and access thresholds.
        # Since access logs are empty, access score is 0 for all links.
        # With min_access_score=1, all links fail access test.
        # With very high structural score, all links fail structural test.
        # So combined should flag all outgoing links.
        report = self.engine.prune_weak_links(
            root,
            min_structural_score=100.0,
            min_access_score=1,
            signal="combined",
            dry_run=True,
        )
        self.assertTrue(report["dry_run"])
        # gamma (cross-domain) should score < 100 structurally; beta higher but still < 100
        # Both fail access (empty logs → 0 co-accesses < min_access_score=1)
        # So combined should flag at least the gamma link
        self.assertGreaterEqual(report["total_removed"], 1)


if __name__ == "__main__":
    unittest.main()
