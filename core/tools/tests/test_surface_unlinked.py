"""Tests for connectivity graph and unlinked-file surfacing in reference_extractor."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ConnectivityGraphTests(unittest.TestCase):
    """Test build_connectivity_graph and classification helpers."""

    def setUp(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            _GOVERNED_REFERENCE_ROOTS,
        )

        self._original_roots = _GOVERNED_REFERENCE_ROOTS
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        # Create a small knowledge tree under memory/knowledge/
        (self.root / "memory" / "knowledge" / "alpha").mkdir(parents=True)
        (self.root / "memory" / "knowledge" / "beta").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, rel_path: str, content: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")

    # -- build_connectivity_graph ------------------------------------------

    def test_graph_counts_edges_within_scope(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            build_connectivity_graph,
        )

        self._write(
            "memory/knowledge/alpha/a.md",
            """\
            ---
            title: A
            ---
            Links to [B](../beta/b.md).
            """,
        )
        self._write(
            "memory/knowledge/beta/b.md",
            """\
            ---
            title: B
            ---
            No links here.
            """,
        )

        graph = build_connectivity_graph(self.root, "memory/knowledge")

        self.assertIn("memory/knowledge/alpha/a.md", graph.outgoing)
        self.assertEqual(
            graph.outgoing["memory/knowledge/alpha/a.md"],
            {"memory/knowledge/beta/b.md"},
        )
        self.assertIn("memory/knowledge/alpha/a.md", graph.incoming["memory/knowledge/beta/b.md"])
        self.assertEqual(graph.scope, "memory/knowledge")

    def test_graph_ignores_out_of_scope_refs(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            build_connectivity_graph,
        )

        self._write(
            "memory/knowledge/alpha/a.md",
            """\
            ---
            title: A
            ---
            Links to [external](https://example.com) and [nonexistent](../../skills/x.md).
            """,
        )

        graph = build_connectivity_graph(self.root, "memory/knowledge")

        self.assertEqual(graph.outgoing.get("memory/knowledge/alpha/a.md", set()), set())

    def test_graph_frontmatter_related_counted(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            build_connectivity_graph,
        )

        self._write(
            "memory/knowledge/alpha/a.md",
            """\
            ---
            title: A
            related:
              - ../beta/b.md
            ---
            Body text.
            """,
        )
        self._write(
            "memory/knowledge/beta/b.md",
            """\
            ---
            title: B
            ---
            No links.
            """,
        )

        graph = build_connectivity_graph(self.root, "memory/knowledge")

        self.assertIn("memory/knowledge/beta/b.md", graph.outgoing["memory/knowledge/alpha/a.md"])

    # -- _classify_file ----------------------------------------------------

    def test_classify_isolated(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _classify_file

        self.assertEqual(_classify_file(0, 0, 2), "isolated")

    def test_classify_sink(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _classify_file

        self.assertEqual(_classify_file(3, 0, 2), "sink")

    def test_classify_source(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _classify_file

        self.assertEqual(_classify_file(0, 3, 2), "source")

    def test_classify_low_connectivity(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _classify_file

        self.assertEqual(_classify_file(1, 1, 2), "low_connectivity")

    def test_classify_well_connected_returns_none(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _classify_file

        self.assertIsNone(_classify_file(3, 3, 2))

    # -- find_unlinked_files -----------------------------------------------

    def test_find_unlinked_returns_isolated_files(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import find_unlinked_files

        self._write(
            "memory/knowledge/alpha/a.md",
            """\
            ---
            title: A
            ---
            Links to [B](../beta/b.md).
            """,
        )
        self._write(
            "memory/knowledge/beta/b.md",
            """\
            ---
            title: B
            ---
            Links to [A](../alpha/a.md).
            """,
        )
        self._write(
            "memory/knowledge/alpha/orphan.md",
            """\
            ---
            title: Orphan
            ---
            No links at all.
            """,
        )

        result = find_unlinked_files(self.root, scope="memory/knowledge")

        self.assertIn("graph_stats", result)
        self.assertIn("candidates", result)
        self.assertIn("budget", result)
        self.assertEqual(result["graph_stats"]["total_files"], 3)

        paths = [c["path"] for c in result["candidates"]]
        self.assertIn("memory/knowledge/alpha/orphan.md", paths)

        orphan = next(c for c in result["candidates"] if "orphan" in c["path"])
        self.assertEqual(orphan["category"], "isolated")
        self.assertEqual(orphan["in_degree"], 0)
        self.assertEqual(orphan["out_degree"], 0)

    def test_find_unlinked_category_filter(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import find_unlinked_files

        self._write(
            "memory/knowledge/alpha/a.md",
            """\
            ---
            title: A
            ---
            Links to [B](../beta/b.md).
            """,
        )
        self._write(
            "memory/knowledge/beta/b.md",
            """\
            ---
            title: B
            ---
            No links.
            """,
        )
        self._write(
            "memory/knowledge/alpha/orphan.md",
            """\
            ---
            title: Orphan
            ---
            No links.
            """,
        )

        result = find_unlinked_files(
            self.root, scope="memory/knowledge", category_filter="isolated"
        )

        categories = {c["category"] for c in result["candidates"]}
        self.assertTrue(categories <= {"isolated"})

    def test_find_unlinked_max_results_truncation(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import find_unlinked_files

        for i in range(5):
            self._write(
                f"memory/knowledge/alpha/file{i}.md",
                f"---\ntitle: File {i}\n---\nNo links.\n",
            )

        result = find_unlinked_files(self.root, scope="memory/knowledge", max_results=2)

        self.assertEqual(len(result["candidates"]), 2)
        self.assertTrue(result["budget"]["truncated"])
        self.assertGreater(result["budget"]["total"], 2)

    def test_find_unlinked_empty_scope_returns_no_candidates(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import find_unlinked_files

        # Empty directory, no .md files
        (self.root / "memory" / "knowledge" / "gamma").mkdir(parents=True, exist_ok=True)

        result = find_unlinked_files(self.root, scope="memory/knowledge/gamma")

        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["graph_stats"]["total_files"], 0)

    def test_find_unlinked_no_suggestions_flag(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import find_unlinked_files

        self._write(
            "memory/knowledge/alpha/orphan.md",
            """\
            ---
            title: Orphan
            ---
            No links.
            """,
        )

        result = find_unlinked_files(self.root, scope="memory/knowledge", include_suggestions=False)

        for c in result["candidates"]:
            self.assertNotIn("suggested_links", c)

    # -- _tokenize_stem ----------------------------------------------------

    def test_tokenize_stem_splits_and_filters(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import _tokenize_stem

        tokens = _tokenize_stem("hardware-efficiency-overview.md")
        self.assertIn("hardware", tokens)
        self.assertIn("efficiency", tokens)
        self.assertNotIn("overview", tokens)  # stop word

    # -- _suggest_link_candidates ------------------------------------------

    def test_suggest_link_candidates_finds_directory_peers(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            _suggest_link_candidates,
            build_connectivity_graph,
        )

        self._write(
            "memory/knowledge/alpha/concept-a.md",
            "---\ntitle: Concept A\n---\nNo links.\n",
        )
        self._write(
            "memory/knowledge/alpha/concept-b.md",
            "---\ntitle: Concept B\n---\nNo links.\n",
        )

        graph = build_connectivity_graph(self.root, "memory/knowledge")
        suggestions = _suggest_link_candidates(
            "memory/knowledge/alpha/concept-a.md", graph, self.root
        )

        targets = [s["target"] for s in suggestions]
        self.assertIn("memory/knowledge/alpha/concept-b.md", targets)

    def test_suggest_link_candidates_scores_stem_overlap(self) -> None:
        from core.tools.agent_memory_mcp.tools.reference_extractor import (
            _suggest_link_candidates,
            build_connectivity_graph,
        )

        self._write(
            "memory/knowledge/alpha/deep-learning-basics.md",
            "---\ntitle: DL Basics\n---\nNo links.\n",
        )
        self._write(
            "memory/knowledge/beta/deep-learning-advanced.md",
            "---\ntitle: DL Advanced\n---\nNo links.\n",
        )
        self._write(
            "memory/knowledge/beta/unrelated-topic.md",
            "---\ntitle: Unrelated\n---\nNo links.\n",
        )

        graph = build_connectivity_graph(self.root, "memory/knowledge")
        suggestions = _suggest_link_candidates(
            "memory/knowledge/alpha/deep-learning-basics.md",
            graph,
            self.root,
        )

        # deep-learning-advanced should rank higher than unrelated-topic
        if suggestions:
            targets = [s["target"] for s in suggestions]
            self.assertIn("memory/knowledge/beta/deep-learning-advanced.md", targets)
            dl_idx = targets.index("memory/knowledge/beta/deep-learning-advanced.md")
            if "memory/knowledge/beta/unrelated-topic.md" in targets:
                unrel_idx = targets.index("memory/knowledge/beta/unrelated-topic.md")
                self.assertLess(dl_idx, unrel_idx)


if __name__ == "__main__":
    unittest.main()
