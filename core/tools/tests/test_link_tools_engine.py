from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_reference_extractor() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.tools.reference_extractor")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(
            f"reference_extractor dependencies unavailable: {exc.name}"
        ) from exc


class LinkToolsEngineTests(unittest.TestCase):
    engine: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_reference_extractor()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _write_files(self, files: dict[str, str]) -> Path:
        root = Path(self._tmpdir.name) / "content"
        for rel_path, content in files.items():
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return root

    def test_resolve_link_diagnostics_handles_relative_and_fragment_only_targets(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/topic/source.md": "# Source\n",
                "memory/knowledge/topic/target.md": "# Target\n\n## Details\n",
            }
        )

        relative_payload = self.engine.resolve_link_diagnostics(
            root,
            "memory/knowledge/topic/source.md",
            "target.md#details",
        )
        fragment_payload = self.engine.resolve_link_diagnostics(
            root,
            "memory/knowledge/topic/source.md",
            "#source",
        )

        self.assertEqual(relative_payload["resolved_path"], "memory/knowledge/topic/target.md")
        self.assertTrue(relative_payload["exists"])
        self.assertEqual(fragment_payload["resolved_path"], "memory/knowledge/topic/source.md")
        self.assertTrue(fragment_payload["is_fragment_only"])

    def test_suggest_links_for_file_uses_body_mentions(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "---\nsource: test\ncreated: 2026-01-01\ntrust: low\n---\n\n# Compression\n\n## Gardenfors Conceptual Spaces\n\nThis note references gardenfors conceptual spaces directly.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/other.md": "# Other\n",
            }
        )

        payload = self.engine.suggest_links_for_file(
            root,
            "memory/knowledge/philosophy/compression.md",
            max_suggestions=5,
        )

        targets = [item["target"] for item in payload["suggestions"]]
        self.assertIn("memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md", targets)
        suggestion = next(
            item
            for item in payload["suggestions"]
            if item["target"]
            == "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md"
        )
        self.assertIn("reasons", suggestion)
        self.assertTrue(any("candidate title" in reason for reason in suggestion["reasons"]))
        self.assertGreaterEqual(payload["candidate_pool_size"], 2)

    def test_suggest_links_for_file_can_filter_cross_domain_only(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nGardenfors conceptual spaces and reasoning both matter here.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/reasoning.md": "# Reasoning\n",
            }
        )

        payload = self.engine.suggest_links_for_file(
            root,
            "memory/knowledge/philosophy/compression.md",
            max_suggestions=5,
            domain_mode="cross",
        )

        self.assertEqual(payload["domain_mode"], "cross")
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertTrue(all(not item["is_same_domain"] for item in payload["suggestions"]))
        self.assertTrue(
            any(
                item["target"]
                == "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md"
                for item in payload["suggestions"]
            )
        )

    def test_suggest_links_for_file_can_filter_by_min_score(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nGardenfors conceptual spaces and reasoning both matter here.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/reasoning.md": "# Reasoning\n",
            }
        )

        payload = self.engine.suggest_links_for_file(
            root,
            "memory/knowledge/philosophy/compression.md",
            max_suggestions=5,
            min_score=5.0,
        )

        self.assertEqual(payload["min_score"], 5.0)
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertTrue(all(item["score"] >= 5.0 for item in payload["suggestions"]))
        self.assertTrue(
            all(
                item["target"]
                != "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md"
                for item in payload["suggestions"]
            )
        )

    def test_summarize_cross_domain_links_counts_directional_pairs(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n\nSee [Compression](../philosophy/compression.md).\n",
            }
        )

        payload = self.engine.summarize_cross_domain_links(root, "memory/knowledge")

        self.assertEqual(payload["domain_count"], 2)
        self.assertGreaterEqual(len(payload["directional_pairs"]), 2)
        self.assertIn("matrix", payload)
        self.assertGreaterEqual(payload["cross_domain_edge_total"], 2)
        self.assertEqual(payload["within_domain_edge_total"], 0)
        self.assertEqual(payload["domains"][0]["top_targets"][0]["edge_count"], 1)

    def test_summarize_cross_domain_links_can_filter_by_source_target_and_min_edges(self) -> None:
        root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\nSee [AI](../ai/frontier.md).\n",
                "memory/knowledge/philosophy/logic.md": "# Logic\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
                "memory/knowledge/ai/frontier.md": "# Frontier\n",
            }
        )

        payload = self.engine.summarize_cross_domain_links(
            root,
            "memory/knowledge",
            source_domain="philosophy",
            target_domain="cognitive-science",
            min_edge_count=2,
        )

        self.assertEqual(payload["source_domain_filter"], "philosophy")
        self.assertEqual(payload["target_domain_filter"], "cognitive-science")
        self.assertEqual(payload["min_edge_count"], 2)
        self.assertEqual(payload["cross_domain_edge_total"], 2)
        self.assertEqual(len(payload["directional_pairs"]), 1)
        self.assertEqual(payload["directional_pairs"][0]["edge_count"], 2)
        self.assertEqual(payload["matrix"][0]["targets"], {"cognitive-science": 2})

    def test_diff_connectivity_graphs_reports_added_edges(self) -> None:
        before_root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
            }
        )
        before_graph = self.engine.build_connectivity_graph(before_root, "memory/knowledge")

        after_root = self._write_files(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
            }
        )
        after_graph = self.engine.build_connectivity_graph(after_root, "memory/knowledge")
        payload = self.engine.diff_connectivity_graphs(after_graph, before_graph)

        self.assertEqual(len(payload["added_edges"]), 1)
        self.assertEqual(payload["removed_edges"], [])
        self.assertEqual(payload["added_domain_pairs"][0]["source_domain"], "philosophy")
        self.assertEqual(
            payload["added_domain_pairs"][0]["target_domain"],
            "cognitive-science",
        )
        self.assertIn("impacted_files_detail", payload)
        self.assertIn("changed_category_counts", payload)
        self.assertTrue(
            any(
                item["path"] == "memory/knowledge/philosophy/compression.md"
                for item in payload["impacted_files_detail"]
            )
        )


if __name__ == "__main__":
    unittest.main()
