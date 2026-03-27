"""Tests for semantic search tools (embedding index, BM25, hybrid ranking).

Unit tests for the EmbeddingIndex, BM25 scorer, helpfulness loader, and
chunking logic run without optional dependencies.  Integration tests that
exercise the full embedding pipeline are skipped when sentence-transformers
is not installed.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.tools.semantic.search_tools import (  # noqa: E402
    _BM25,
    EmbeddingIndex,
    _check_embedding_deps,
    _load_helpfulness_map,
    _tokenize,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HAS_EMBEDDINGS = _check_embedding_deps()
_skip_no_embeddings = pytest.mark.skipif(
    not _HAS_EMBEDDINGS,
    reason="sentence-transformers not installed",
)


def _write_md(root: Path, rel_path: str, content: str) -> Path:
    """Write a markdown file under *root* and return its Path."""
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tokeniser tests
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World!") == ["hello", "world"]

    def test_empty(self):
        assert _tokenize("") == []

    def test_unicode(self):
        tokens = _tokenize("café naïve")
        assert "café" in tokens
        assert "naïve" in tokens


# ---------------------------------------------------------------------------
# BM25 scorer tests
# ---------------------------------------------------------------------------


class TestBM25:
    def test_basic_scoring(self):
        corpus = [
            ["the", "cat", "sat", "on", "the", "mat"],
            ["the", "dog", "chased", "the", "cat"],
            ["birds", "fly", "in", "the", "sky"],
        ]
        bm25 = _BM25(corpus)

        # "cat" appears in docs 0 and 1 — both should score > 0
        scores = [bm25.score(["cat"], i) for i in range(3)]
        assert scores[0] > 0
        assert scores[1] > 0
        assert scores[2] == 0.0  # no "cat" in doc 2

    def test_idf_effect(self):
        # Rare terms should get higher IDF
        corpus = [
            ["common", "common", "rare"],
            ["common", "common"],
            ["common"],
        ]
        bm25 = _BM25(corpus)
        score_rare = bm25.score(["rare"], 0)
        score_common = bm25.score(["common"], 0)
        assert score_rare > 0
        assert score_common > 0

    def test_empty_corpus(self):
        bm25 = _BM25([])
        assert bm25.corpus_size == 0

    def test_no_match(self):
        corpus = [["apple", "banana"]]
        bm25 = _BM25(corpus)
        assert bm25.score(["cherry"], 0) == 0.0


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------


class TestChunkFile:
    def test_heading_splits(self):
        content = textwrap.dedent("""\
            ---
            title: Test
            ---

            ## Section One

            Content of section one.

            ## Section Two

            Content of section two.
        """)
        chunks = EmbeddingIndex._chunk_file(content)
        assert len(chunks) == 2
        assert chunks[0][0] == "## Section One"
        assert "section one" in chunks[0][1].lower()
        assert chunks[1][0] == "## Section Two"

    def test_no_headings(self):
        content = "Just a plain paragraph of text."
        chunks = EmbeddingIndex._chunk_file(content)
        assert len(chunks) == 1
        assert chunks[0][0] is None

    def test_frontmatter_stripped(self):
        content = "---\ntitle: Hello\n---\nBody text here."
        chunks = EmbeddingIndex._chunk_file(content)
        assert len(chunks) == 1
        assert "title:" not in chunks[0][1]
        assert "Body text here" in chunks[0][1]

    def test_large_chunk_split(self):
        # Generate a chunk larger than CHUNK_MAX_TOKENS
        big_text = " ".join(["word"] * 1000)
        content = f"## Big Section\n\n{big_text}"
        chunks = EmbeddingIndex._chunk_file(content)
        assert len(chunks) > 1
        for heading, text in chunks:
            assert heading == "## Big Section"

    def test_empty_content(self):
        chunks = EmbeddingIndex._chunk_file("")
        assert chunks == []

    def test_only_frontmatter(self):
        content = "---\ntitle: Hello\n---\n"
        chunks = EmbeddingIndex._chunk_file(content)
        assert chunks == []


# ---------------------------------------------------------------------------
# Helpfulness loader tests
# ---------------------------------------------------------------------------


class TestHelpfulnessMap:
    def test_loads_entries(self, tmp_path):
        knowledge_dir = tmp_path / "memory" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        entries = [
            json.dumps({"file": "memory/knowledge/foo.md", "helpfulness": 0.8}),
            json.dumps({"file": "memory/knowledge/foo.md", "helpfulness": 0.6}),
            json.dumps({"file": "memory/knowledge/bar.md", "helpfulness": 1.0}),
        ]
        (knowledge_dir / "ACCESS.jsonl").write_text("\n".join(entries) + "\n", encoding="utf-8")
        result = _load_helpfulness_map(tmp_path)
        assert result["memory/knowledge/foo.md"] == pytest.approx(0.7, abs=0.01)
        assert result["memory/knowledge/bar.md"] == pytest.approx(1.0)

    def test_empty_access(self, tmp_path):
        knowledge_dir = tmp_path / "memory" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "ACCESS.jsonl").write_text("", encoding="utf-8")
        result = _load_helpfulness_map(tmp_path)
        assert result == {}

    def test_missing_files(self, tmp_path):
        result = _load_helpfulness_map(tmp_path)
        assert result == {}

    def test_malformed_json_skipped(self, tmp_path):
        knowledge_dir = tmp_path / "memory" / "knowledge"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "ACCESS.jsonl").write_text(
            "not json\n" + json.dumps({"file": "a.md", "helpfulness": 0.5}) + "\n",
            encoding="utf-8",
        )
        result = _load_helpfulness_map(tmp_path)
        assert result["a.md"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# EmbeddingIndex database tests (no model needed)
# ---------------------------------------------------------------------------


class TestEmbeddingIndexDB:
    def test_ensure_db_creates_tables(self, tmp_path):
        # We can instantiate the index without the model (just DB setup)
        # by creating content_root structure
        content_root = tmp_path / "core"
        content_root.mkdir()
        idx = EmbeddingIndex(tmp_path, content_root)
        assert idx.db_path.exists()

        with sqlite3.connect(str(idx.db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "chunks" in tables
            assert "file_meta" in tables

    def test_needs_reindex_missing_file(self, tmp_path):
        content_root = tmp_path / "core"
        content_root.mkdir()
        idx = EmbeddingIndex(tmp_path, content_root)
        assert idx._needs_reindex("some/file.md", 12345.0) is True

    def test_chunk_count_empty(self, tmp_path):
        content_root = tmp_path / "core"
        content_root.mkdir()
        idx = EmbeddingIndex(tmp_path, content_root)
        assert idx.chunk_count() == 0


# ---------------------------------------------------------------------------
# Integration tests (require sentence-transformers)
# ---------------------------------------------------------------------------


@_skip_no_embeddings
class TestEmbeddingIntegration:
    def test_index_and_search(self, tmp_path):
        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        knowledge.mkdir(parents=True)

        _write_md(
            content_root,
            "memory/knowledge/ai.md",
            textwrap.dedent("""\
                ---
                title: AI Overview
                trust: medium
                created: 2026-01-15
                ---

                ## Machine Learning

                Deep learning models use neural networks with multiple layers.

                ## Natural Language Processing

                NLP enables computers to understand human language.
            """),
        )
        _write_md(
            content_root,
            "memory/knowledge/cooking.md",
            textwrap.dedent("""\
                ---
                title: Cooking Tips
                trust: low
                created: 2025-06-01
                ---

                ## Baking

                Bread requires flour, water, yeast, and salt.
            """),
        )

        idx = EmbeddingIndex(tmp_path, content_root)
        stats = idx.build_index()
        assert stats["indexed"] >= 2
        assert stats["errors"] == 0
        assert idx.chunk_count() > 0

        results = idx.search_vectors("neural networks deep learning")
        assert len(results) > 0
        # The AI file should rank higher for this query
        top_file = results[0]["file_path"]
        assert "ai.md" in top_file

    def test_incremental_reindex(self, tmp_path):
        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        knowledge.mkdir(parents=True)

        md = _write_md(content_root, "memory/knowledge/test.md", "## Hello\n\nWorld.")
        idx = EmbeddingIndex(tmp_path, content_root)
        stats1 = idx.build_index()
        assert stats1["indexed"] == 1

        # Second build without changes should skip
        stats2 = idx.build_index()
        assert stats2["indexed"] == 0
        assert stats2["skipped"] == 1

        # Modify file -> should re-index
        import time

        time.sleep(0.05)  # Ensure mtime changes
        md.write_text("## Updated\n\nNew content.", encoding="utf-8")
        stats3 = idx.build_index()
        assert stats3["indexed"] == 1

    def test_force_reindex(self, tmp_path):
        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        knowledge.mkdir(parents=True)
        _write_md(content_root, "memory/knowledge/test.md", "## Hello\n\nWorld.")

        idx = EmbeddingIndex(tmp_path, content_root)
        idx.build_index()
        stats = idx.build_index(force=True)
        assert stats["indexed"] == 1
        assert stats["skipped"] == 0

    def test_scope_filter(self, tmp_path):
        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        skills = content_root / "memory" / "skills"
        knowledge.mkdir(parents=True)
        skills.mkdir(parents=True)

        _write_md(content_root, "memory/knowledge/a.md", "## Topic A\n\nAlpha content.")
        _write_md(content_root, "memory/skills/b.md", "## Skill B\n\nBeta content.")

        idx = EmbeddingIndex(tmp_path, content_root)
        idx.build_index()

        # Scope to knowledge only
        results = idx.search_vectors("content", scope="memory/knowledge")
        file_paths = {r["file_path"] for r in results}
        assert all("knowledge" in fp for fp in file_paths)

    def test_removed_files_pruned(self, tmp_path):
        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        knowledge.mkdir(parents=True)

        md = _write_md(content_root, "memory/knowledge/test.md", "## Hello\n\nWorld.")
        idx = EmbeddingIndex(tmp_path, content_root)
        idx.build_index()
        assert idx.chunk_count() > 0

        # Delete the file and rebuild
        md.unlink()
        stats = idx.build_index()
        assert stats["removed"] == 1
        assert idx.chunk_count() == 0


# ---------------------------------------------------------------------------
# MCP tool integration tests (require sentence-transformers)
# ---------------------------------------------------------------------------


@_skip_no_embeddings
class TestSemanticSearchTool:
    """Test the memory_semantic_search MCP tool end-to-end."""

    @pytest.fixture()
    def tool_env(self, tmp_path):
        """Set up a minimal MCP environment with indexed files."""
        import subprocess

        content_root = tmp_path / "core"
        knowledge = content_root / "memory" / "knowledge"
        knowledge.mkdir(parents=True)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        _write_md(
            content_root,
            "memory/knowledge/philosophy.md",
            textwrap.dedent("""\
                ---
                title: Philosophy of Mind
                trust: high
                created: 2026-03-01
                last_verified: 2026-03-25
                ---

                ## Consciousness

                The hard problem of consciousness asks why physical processes
                give rise to subjective experience.

                ## Personal Identity

                Questions about what makes a person the same over time.
            """),
        )
        _write_md(
            content_root,
            "memory/knowledge/cooking.md",
            textwrap.dedent("""\
                ---
                title: Cooking Basics
                trust: low
                created: 2024-01-01
                ---

                ## Baking Bread

                Bread requires flour, water, yeast, and patience.
            """),
        )

        # Add ACCESS.jsonl with helpfulness data
        access_entries = [
            json.dumps({"file": "memory/knowledge/philosophy.md", "helpfulness": 0.9}),
            json.dumps({"file": "memory/knowledge/philosophy.md", "helpfulness": 0.8}),
            json.dumps({"file": "memory/knowledge/cooking.md", "helpfulness": 0.3}),
        ]
        (knowledge / "ACCESS.jsonl").write_text("\n".join(access_entries) + "\n", encoding="utf-8")

        # Git add all
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        # Create MCP environment
        from core.tools.agent_memory_mcp.git_repo import GitRepo
        from core.tools.agent_memory_mcp.tools.semantic.search_tools import register_tools

        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError:
            pytest.skip("mcp not installed")

        repo = GitRepo(tmp_path, content_prefix="core")
        mcp_app = FastMCP("test")
        tools = register_tools(
            mcp_app,
            lambda: repo,
            lambda: repo.content_root,
        )

        return {
            "tmp_path": tmp_path,
            "content_root": content_root,
            "repo": repo,
            "tools": tools,
        }

    @pytest.mark.asyncio
    async def test_search_returns_results(self, tool_env):
        search = tool_env["tools"]["memory_semantic_search"]
        result = await search("consciousness subjective experience")
        assert "philosophy.md" in result
        assert "combined:" in result

    @pytest.mark.asyncio
    async def test_trust_filter(self, tool_env):
        search = tool_env["tools"]["memory_semantic_search"]
        result = await search(
            "food recipes",
            min_trust="high",
        )
        # cooking.md has trust: low, should be filtered
        assert "cooking.md" not in result

    @pytest.mark.asyncio
    async def test_helpfulness_boosts(self, tool_env):
        search = tool_env["tools"]["memory_semantic_search"]
        result = await search(
            "knowledge",
            helpfulness_weight=0.8,
            vector_weight=0.1,
            bm25_weight=0.1,
            freshness_weight=0.0,
        )
        # Philosophy has higher helpfulness (0.85) vs cooking (0.3)
        lines = result.split("\n")
        first_file_line = next((ln for ln in lines if ln.startswith("**1.")), "")
        assert "philosophy.md" in first_file_line

    @pytest.mark.asyncio
    async def test_reindex_tool(self, tool_env):
        reindex = tool_env["tools"]["memory_reindex"]
        result = await reindex(force=True)
        assert "Reindex complete" in result
        assert "Indexed:" in result

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, tool_env):
        from core.tools.agent_memory_mcp.errors import ValidationError

        search = tool_env["tools"]["memory_semantic_search"]
        with pytest.raises(ValidationError):
            await search("")


# ---------------------------------------------------------------------------
# Graceful degradation tests (no embedding deps required)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_check_returns_bool(self):
        result = _check_embedding_deps()
        assert isinstance(result, bool)

    def test_model_import_error_message(self, tmp_path):
        """When embeddings unavailable, model access gives clear error."""
        content_root = tmp_path / "core"
        content_root.mkdir()
        idx = EmbeddingIndex(tmp_path, content_root)

        if _HAS_EMBEDDINGS:
            pytest.skip("sentence-transformers is installed; cannot test missing dep")

        with pytest.raises(ImportError, match="sentence-transformers"):
            _ = idx.model
