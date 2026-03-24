"""Tests for the graph analysis engine and MCP tools."""

from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, ClassVar, Coroutine, cast

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def _load_engine():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.tools.graph_analysis")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"graph_analysis dependencies unavailable: {exc.name}") from exc


def _load_server():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


# ── Fixtures ───────────────────────────────────────────────────────


def _make_md(title: str, related: list[str] | None = None, body: str = "") -> str:
    lines = ["---", f"title: {title}", "source: test", "created: 2026-01-01", "trust: low"]
    if related:
        lines.append("related: " + ", ".join(related))
    lines.append("---\n")
    if body:
        lines.append(body)
    return "\n".join(lines)


_SEED_FILES: dict[str, str] = {
    "memory/knowledge/math/algebra.md": _make_md(
        "Algebra",
        related=["topology.md"],
        body="See also [Topology](topology.md) and [Analysis](analysis.md).\n",
    ),
    "memory/knowledge/math/topology.md": _make_md(
        "Topology",
        body="Related to [Algebra](algebra.md).\n",
    ),
    "memory/knowledge/math/analysis.md": _make_md(
        "Analysis",
        body="Foundational for [Algebra](algebra.md).\n",
    ),
    "memory/knowledge/math/orphan.md": _make_md("Orphan"),
    "memory/knowledge/phil/epistemology.md": _make_md(
        "Epistemology",
        body="Connects to [Algebra](../math/algebra.md).\n",
    ),
}


# File with redundant links for prune tests
_PRUNE_FILES: dict[str, str] = {
    "memory/knowledge/math/redundant.md": _make_md(
        "Redundant",
        body=(
            "Body link to [Algebra](algebra.md) and [Topology](topology.md).\n"
            "Duplicate body link to [Algebra](algebra.md).\n\n"
            "---\n\n## Connections\n\n"
            "- [Algebra](algebra.md)\n"
            "- [Analysis](analysis.md)\n"
            "- [Analysis](analysis.md)\n"
        ),
    ),
}


# ── Engine unit tests ──────────────────────────────────────────────


class GraphAnalysisEngineTests(unittest.TestCase):
    engine: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _load_engine()

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

    # -- build_knowledge_graph --

    def test_build_graph_discovers_nodes_and_edges(self) -> None:
        root = self._write_files(_SEED_FILES)
        graph = self.engine.build_knowledge_graph(root)
        ids = {n["id"] for n in graph["nodes"]}

        self.assertIn("memory/knowledge/math/algebra.md", ids)
        self.assertIn("memory/knowledge/math/topology.md", ids)
        self.assertIn("memory/knowledge/phil/epistemology.md", ids)
        self.assertGreaterEqual(len(graph["edges"]), 3)

    def test_build_graph_scoped_to_domain(self) -> None:
        root = self._write_files(_SEED_FILES)
        graph = self.engine.build_knowledge_graph(root, scope="knowledge/math")

        # All primary nodes should be in 'math'
        for n in graph["nodes"]:
            if n["id"].startswith("memory/knowledge/math/"):
                self.assertEqual(n["domain"], "math")

    def test_build_graph_deduplicates_edges(self) -> None:
        root = self._write_files(_SEED_FILES)
        graph = self.engine.build_knowledge_graph(root)
        edge_set = {(e["source"], e["target"]) for e in graph["edges"]}
        # No (a,b) and (b,a)
        for s, t in edge_set:
            self.assertNotIn((t, s), edge_set)

    # -- analyze_graph --

    def test_analyze_graph_returns_metrics(self) -> None:
        root = self._write_files(_SEED_FILES)
        graph = self.engine.build_knowledge_graph(root)
        metrics = self.engine.analyze_graph(graph["nodes"], graph["edges"])

        self.assertFalse(metrics["insufficient"])
        self.assertIn("avg_degree", metrics)
        self.assertIn("avg_clustering", metrics)
        self.assertIn("sigma", metrics)
        self.assertIn("domains", metrics)
        self.assertIsInstance(metrics["bridges"], list)
        self.assertIsInstance(metrics["hubs"], list)
        self.assertIsInstance(metrics["orphans"], list)

    def test_analyze_graph_insufficient_for_tiny(self) -> None:
        metrics = self.engine.analyze_graph([{"id": "a", "domain": "x"}], [])
        self.assertTrue(metrics["insufficient"])

    # -- find_duplicate_links --

    def test_find_duplicate_links_detects_duplicates(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._write_files(files)
        dupes = self.engine.find_duplicate_links(root)

        dupe_paths = {d["path"] for d in dupes}
        self.assertIn("memory/knowledge/math/redundant.md", dupe_paths)

        entry = next(d for d in dupes if d["path"] == "memory/knowledge/math/redundant.md")
        kinds = {d["kind"] for d in entry["duplicates"]}
        self.assertIn("connections_duplicates_body", kinds)
        self.assertIn("duplicate_body_link", kinds)
        self.assertIn("duplicate_connections_link", kinds)

    # -- prune_redundant_links --

    def test_prune_dry_run_reports_without_writing(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._write_files(files)
        original = (root / "memory/knowledge/math/redundant.md").read_text(encoding="utf-8")

        report = self.engine.prune_redundant_links(root, dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertGreater(report["total_removed"], 0)

        after = (root / "memory/knowledge/math/redundant.md").read_text(encoding="utf-8")
        self.assertEqual(original, after, "dry_run should not modify files")

    def test_prune_applies_changes(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._write_files(files)

        report = self.engine.prune_redundant_links(root, dry_run=False)
        self.assertFalse(report["dry_run"])
        self.assertGreater(report["total_removed"], 0)
        self.assertIn("memory/knowledge/math/redundant.md", report["files_modified"])

        # Verify duplicates are gone
        dupes_after = self.engine.find_duplicate_links(root, scope="knowledge/math")
        redundant_dupes = [
            d for d in dupes_after if d["path"] == "memory/knowledge/math/redundant.md"
        ]
        self.assertEqual(redundant_dupes, [], "all duplicates should be removed after prune")


# ── MCP tool integration tests ────────────────────────────────────


class GraphToolsMCPTests(unittest.TestCase):
    server: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = _load_server()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _init_repo(self, files: dict[str, str]) -> Path:
        temp_root = Path(self._tmpdir.name) / f"repo_{id(files)}"
        temp_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=temp_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )

        for rel_path, content in files.items():
            target = temp_root / "core" / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=temp_root, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return temp_root / "core"

    def _create_tools(self, repo_root: Path) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(repo_root=repo_root)
        return cast(dict[str, ToolCallable], tools)

    def test_memory_analyze_graph_tool(self) -> None:
        root = self._init_repo(_SEED_FILES)
        tools = self._create_tools(root)
        result = json.loads(asyncio.run(tools["memory_analyze_graph"](path="")))

        self.assertIn("metrics", result)
        self.assertFalse(result["metrics"]["insufficient"])
        self.assertNotIn("duplicate_links", result)

    def test_memory_analyze_graph_with_details(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._init_repo(files)
        tools = self._create_tools(root)
        result = json.loads(
            asyncio.run(tools["memory_analyze_graph"](path="", include_details=True))
        )

        self.assertIn("duplicate_links", result)
        self.assertIsInstance(result["duplicate_links"], list)

    def test_memory_prune_redundant_links_dry_run(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._init_repo(files)
        tools = self._create_tools(root)
        result = json.loads(
            asyncio.run(tools["memory_prune_redundant_links"](path="", dry_run=True))
        )

        self.assertTrue(result["dry_run"])
        self.assertGreater(result["total_removed"], 0)

    def test_memory_prune_redundant_links_commits(self) -> None:
        files = {**_SEED_FILES, **_PRUNE_FILES}
        root = self._init_repo(files)
        tools = self._create_tools(root)
        result = json.loads(
            asyncio.run(tools["memory_prune_redundant_links"](path="", dry_run=False))
        )

        self.assertIn("commit_sha", result)
        self.assertIsNotNone(result["commit_sha"])
        self.assertIn("[curation]", result["commit_message"])
        self.assertGreater(len(result["files_changed"]), 0)


if __name__ == "__main__":
    unittest.main()
