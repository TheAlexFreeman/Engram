"""Semantic search tools for memory retrieval.

Provides vector-based semantic search with optional BM25 hybrid scoring,
freshness weighting, and ACCESS.jsonl helpfulness reranking.

Requires optional dependency: pip install agent-memory-mcp[search]
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...git_repo import GitRepo

# ---------------------------------------------------------------------------
# Lazy optional-dependency check
# ---------------------------------------------------------------------------

_EMBEDDING_AVAILABLE: bool | None = None


def _check_embedding_deps() -> bool:
    global _EMBEDDING_AVAILABLE
    if _EMBEDDING_AVAILABLE is None:
        try:
            import numpy  # noqa: F401
            from sentence_transformers import SentenceTransformer  # noqa: F401

            _EMBEDDING_AVAILABLE = True
        except ImportError:
            _EMBEDDING_AVAILABLE = False
    return _EMBEDDING_AVAILABLE


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DB_DIR = ".engram"
DB_NAME = "search.db"
CHUNK_TARGET_TOKENS = 512
CHUNK_MAX_TOKENS = 768
DEFAULT_SCOPES = ("memory/knowledge", "memory/skills", "memory/users")

# BM25 parameters
BM25_K1 = 1.2
BM25_B = 0.75

# Default hybrid weights: vector, bm25, freshness, helpfulness
DEFAULT_VECTOR_WEIGHT = 0.4
DEFAULT_BM25_WEIGHT = 0.3
DEFAULT_FRESHNESS_WEIGHT = 0.15
DEFAULT_HELPFULNESS_WEIGHT = 0.15

_HEADING_RE = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


# ---------------------------------------------------------------------------
# Tokenisation helpers (used by BM25)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser, lowercased."""
    return _WORD_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# Embedding index
# ---------------------------------------------------------------------------


class EmbeddingIndex:
    """Manages a local SQLite-backed embedding index for memory files."""

    def __init__(self, repo_root: Path, content_root: Path, model_name: str = DEFAULT_MODEL):
        self.repo_root = repo_root
        self.content_root = content_root
        self.db_path = repo_root / DB_DIR / DB_NAME
        self.model_name = model_name
        self._model: Any = None
        self._ensure_db()

    # -- database setup ----------------------------------------------------

    def _ensure_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    chunk_idx INTEGER NOT NULL,
                    heading TEXT,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    UNIQUE(file_path, chunk_idx)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_meta (
                    file_path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    model_name TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_path)")

    # -- model access (lazy) -----------------------------------------------

    @property
    def model(self) -> Any:
        if self._model is None:
            if not _check_embedding_deps():
                raise ImportError(
                    "sentence-transformers is required for semantic search. "
                    "Install with: pip install agent-memory-mcp[search]"
                )
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    # -- incremental indexing ----------------------------------------------

    def _needs_reindex(self, file_path: str, mtime: float) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT mtime, model_name FROM file_meta WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            if row is None:
                return True
            return row[0] < mtime or row[1] != self.model_name

    @staticmethod
    def _chunk_file(content: str) -> list[tuple[str | None, str]]:
        """Split file content into chunks at ## headings.

        Returns list of ``(heading, chunk_text)`` tuples.
        """
        body = content
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                body = content[end + 3 :].strip()

        parts = _HEADING_RE.split(body)
        chunks: list[tuple[str | None, str]] = []
        current_heading: str | None = None
        current_text = ""
        for part in parts:
            if _HEADING_RE.match(part):
                if current_text.strip():
                    chunks.append((current_heading, current_text.strip()))
                current_heading = part.strip()
                current_text = ""
            else:
                current_text += part
        if current_text.strip():
            chunks.append((current_heading, current_text.strip()))
        if not chunks and body.strip():
            chunks = [(None, body.strip())]

        # Sub-split oversized chunks
        result: list[tuple[str | None, str]] = []
        for heading, text in chunks:
            words = text.split()
            if len(words) > CHUNK_MAX_TOKENS:
                for i in range(0, len(words), CHUNK_TARGET_TOKENS):
                    result.append((heading, " ".join(words[i : i + CHUNK_TARGET_TOKENS])))
            else:
                result.append((heading, text))
        return result

    def index_file(self, rel_path: str, content: str, mtime: float) -> int:
        """Index a single file. Returns number of chunks created."""
        chunks = self._chunk_file(content)
        if not chunks:
            return 0

        texts = [f"{h}: {t}" if h else t for h, t in chunks]
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (rel_path,))
            for idx, ((heading, text), emb) in enumerate(zip(chunks, embeddings)):
                conn.execute(
                    "INSERT INTO chunks (file_path, chunk_idx, heading, content, embedding) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rel_path, idx, heading, text, emb.tobytes()),
                )
            conn.execute(
                "INSERT OR REPLACE INTO file_meta (file_path, mtime, model_name) VALUES (?, ?, ?)",
                (rel_path, mtime, self.model_name),
            )
        return len(chunks)

    def remove_file(self, rel_path: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (rel_path,))
            conn.execute("DELETE FROM file_meta WHERE file_path = ?", (rel_path,))

    def build_index(
        self,
        scopes: list[str] | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        """Build or update the embedding index.

        Args:
            scopes: Folder paths relative to content root to index.
            force: Re-index all files regardless of mtime.

        Returns:
            Stats dict with indexed/skipped/removed/errors counts.
        """
        if scopes is None:
            scopes = list(DEFAULT_SCOPES)

        stats = {"indexed": 0, "skipped": 0, "removed": 0, "errors": 0}
        seen_files: set[str] = set()

        for scope in scopes:
            scope_path = self.content_root / scope
            if not scope_path.is_dir():
                continue
            for md_file in scope_path.rglob("*.md"):
                rel_path = str(md_file.relative_to(self.content_root)).replace("\\", "/")
                seen_files.add(rel_path)
                mtime = md_file.stat().st_mtime

                if not force and not self._needs_reindex(rel_path, mtime):
                    stats["skipped"] += 1
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                    self.index_file(rel_path, content, mtime)
                    stats["indexed"] += 1
                except Exception:
                    stats["errors"] += 1

        # Prune deleted files — only within the requested scopes so
        # that a partial rebuild does not remove chunks from untouched scopes.
        scope_prefixes = tuple(s.rstrip("/") + "/" for s in scopes)
        with sqlite3.connect(str(self.db_path)) as conn:
            indexed_files = {
                row[0] for row in conn.execute("SELECT file_path FROM file_meta").fetchall()
            }
        for old_file in indexed_files - seen_files:
            if any(old_file.startswith(prefix) for prefix in scope_prefixes):
                self.remove_file(old_file)
                stats["removed"] += 1

        return stats

    def search_vectors(
        self,
        query: str,
        limit: int | None = 30,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return chunks ranked by cosine similarity to *query*.

        When *limit* is ``None`` all matching chunks are returned (useful
        when post-retrieval filtering such as trust filtering is planned).
        """
        import numpy as np

        query_emb = self.model.encode([query], normalize_embeddings=True)[0]

        with sqlite3.connect(str(self.db_path)) as conn:
            sql = "SELECT file_path, chunk_idx, heading, content, embedding FROM chunks"
            params: list[str] = []
            if scope:
                sql += " WHERE file_path LIKE ?"
                params.append(f"{scope}%")
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        results: list[dict[str, Any]] = []
        for file_path, chunk_idx, heading, content, emb_bytes in rows:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            similarity = float(np.dot(query_emb, emb))
            results.append(
                {
                    "file_path": file_path,
                    "chunk_idx": chunk_idx,
                    "heading": heading,
                    "content": content,
                    "similarity": similarity,
                }
            )
        results.sort(key=lambda x: x["similarity"], reverse=True)
        if limit is not None:
            return results[:limit]
        return results

    def chunk_count(self) -> int:
        """Return total number of indexed chunks."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
            return row[0] if row else 0


# ---------------------------------------------------------------------------
# BM25 scoring (self-contained, no external deps)
# ---------------------------------------------------------------------------


class _BM25:
    """Lightweight BM25 scorer over a pre-tokenised corpus."""

    def __init__(self, corpus_tokens: list[list[str]]) -> None:
        self.corpus_size = len(corpus_tokens)
        self.doc_lens = [len(doc) for doc in corpus_tokens]
        self.avgdl = sum(self.doc_lens) / max(self.corpus_size, 1)
        self.df: dict[str, int] = defaultdict(int)
        for doc in corpus_tokens:
            for term in set(doc):
                self.df[term] += 1
        self.corpus_tokens = corpus_tokens

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        doc = self.corpus_tokens[doc_idx]
        tf = Counter(doc)
        doc_len = self.doc_lens[doc_idx]
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            n_t = self.df.get(term, 0)
            idf = math.log((self.corpus_size - n_t + 0.5) / (n_t + 0.5) + 1.0)
            term_freq = tf[term]
            numerator = term_freq * (BM25_K1 + 1)
            denominator = term_freq + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / self.avgdl)
            score += idf * numerator / denominator
        return score


# ---------------------------------------------------------------------------
# ACCESS.jsonl helpfulness loader
# ---------------------------------------------------------------------------


def _load_helpfulness_map(content_root: Path) -> dict[str, float]:
    """Load mean helpfulness per file from ACCESS.jsonl files.

    Returns mapping of content-relative file path -> mean helpfulness [0,1].
    """
    helpfulness_sums: dict[str, float] = defaultdict(float)
    helpfulness_counts: dict[str, int] = defaultdict(int)

    access_files = [
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        content_root / "memory" / "skills" / "ACCESS.jsonl",
        content_root / "memory" / "users" / "ACCESS.jsonl",
        content_root / "memory" / "activity" / "ACCESS.jsonl",
    ]

    for access_path in access_files:
        if not access_path.exists():
            continue
        try:
            text = access_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            file_path = entry.get("file", "")
            raw_h = entry.get("helpfulness")
            if file_path and raw_h is not None:
                try:
                    h = float(raw_h)
                    helpfulness_sums[file_path] += h
                    helpfulness_counts[file_path] += 1
                except (ValueError, TypeError):
                    pass

    result: dict[str, float] = {}
    for fp, total in helpfulness_sums.items():
        count = helpfulness_counts[fp]
        if count > 0:
            result[fp] = total / count
    return result


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_tools(
    mcp: "FastMCP",
    get_repo: "Any",
    get_root: "Any",
) -> dict[str, object]:
    """Register semantic search tools."""

    _index_cache: dict[str, EmbeddingIndex] = {}

    def _get_index() -> EmbeddingIndex:
        repo: GitRepo = get_repo()
        root: Path = get_root()
        cache_key = str(root)
        if cache_key not in _index_cache:
            _index_cache[cache_key] = EmbeddingIndex(repo.root, root)
        return _index_cache[cache_key]

    # ------------------------------------------------------------------
    # memory_semantic_search
    # ------------------------------------------------------------------

    @mcp.tool(
        name="memory_semantic_search",
        annotations=_tool_annotations(
            title="Semantic Memory Search",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_semantic_search(
        query: str,
        scope: str | None = None,
        limit: int = 10,
        min_trust: str | None = None,
        freshness_weight: float = DEFAULT_FRESHNESS_WEIGHT,
        helpfulness_weight: float = DEFAULT_HELPFULNESS_WEIGHT,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
    ) -> str:
        """Search memory using semantic similarity with hybrid ranking.

        Combines vector similarity, BM25 keyword matching, temporal freshness,
        and ACCESS.jsonl helpfulness into a single ranked result set.

        Requires ``sentence-transformers`` (install with
        ``pip install agent-memory-mcp[search]``). If unavailable, returns
        an error message instead of results.

        The embedding index is built lazily on first search and updated
        incrementally on subsequent calls. Use ``memory_reindex`` to force
        a full rebuild. Call ``memory_tool_schema`` with
        ``"memory_semantic_search"`` for the filter and weighting contract.

        Args:
            query:              Natural language search query.
            scope:              Folder path (content-relative) to restrict
                                search, e.g. ``memory/knowledge/philosophy``.
            limit:              Maximum results to return (default 10, max 50).
            min_trust:          Filter by minimum trust level
                                (``low`` | ``medium`` | ``high``).
            freshness_weight:   Weight for temporal freshness (default 0.15).
            helpfulness_weight: Weight for ACCESS.jsonl helpfulness (default 0.15).
            vector_weight:      Weight for vector similarity (default 0.4).
            bm25_weight:        Weight for BM25 keyword score (default 0.3).
        """
        from ...errors import ValidationError

        if not _check_embedding_deps():
            return (
                "⚠️ sentence-transformers is not installed. "
                "Semantic search is unavailable. "
                "Install with: pip install agent-memory-mcp[search]"
            )

        if not query or not query.strip():
            raise ValidationError("query must be a non-empty string")

        limit = max(1, min(limit, 50))

        # Clamp weights to [0, 1]
        vector_weight = max(0.0, min(1.0, vector_weight))
        bm25_weight = max(0.0, min(1.0, bm25_weight))
        freshness_weight = max(0.0, min(1.0, freshness_weight))
        helpfulness_weight = max(0.0, min(1.0, helpfulness_weight))

        root = get_root()
        index = _get_index()

        # Ensure index is up to date
        index.build_index()

        if index.chunk_count() == 0:
            return "No files indexed. The memory repository may be empty."

        # 1) Vector similarity — when trust filtering is active, fetch
        # the full candidate set so high-trust matches are not dropped
        # before the filter runs.
        vector_limit = None if min_trust else limit * 3
        vector_results = index.search_vectors(query, limit=vector_limit, scope=scope)
        if not vector_results:
            return f"No results found for: {query}"

        # 2) Freshness + trust metadata (needed before trust filtering)
        from ...freshness import effective_date, freshness_score
        from ...frontmatter_utils import read_with_frontmatter

        freshness_cache: dict[str, float] = {}
        trust_cache: dict[str, str] = {}
        for r in vector_results:
            fp = r["file_path"]
            if fp not in freshness_cache:
                abs_path = root / fp
                if abs_path.exists():
                    try:
                        fm, _ = read_with_frontmatter(abs_path)
                        ref_date = effective_date(fm)
                        freshness_cache[fp] = freshness_score(ref_date)
                        trust_cache[fp] = str(fm.get("trust", "")).lower()
                    except Exception:
                        freshness_cache[fp] = 0.0
                        trust_cache[fp] = ""
                else:
                    freshness_cache[fp] = 0.0
                    trust_cache[fp] = ""

        # 3) Trust filtering — applied before truncation so qualifying
        # matches are never dropped by the candidate-pool limit.
        trust_levels = {"low": 0, "medium": 1, "high": 2}
        if min_trust and min_trust.lower() in trust_levels:
            min_trust_level = trust_levels[min_trust.lower()]
            vector_results = [
                r
                for r in vector_results
                if trust_levels.get(trust_cache.get(r["file_path"], ""), 0) >= min_trust_level
            ]

        # Truncate to a manageable candidate pool after trust filtering
        vector_results = vector_results[: limit * 3]

        if not vector_results:
            return f"No results found for: {query}"

        # 4) BM25 scoring over matched chunks
        corpus_tokens = [_tokenize(r["content"]) for r in vector_results]
        bm25 = _BM25(corpus_tokens)
        query_tokens = _tokenize(query)
        for i, result in enumerate(vector_results):
            result["bm25"] = bm25.score(query_tokens, i)

        # Normalise BM25 scores to [0, 1]
        max_bm25 = max((r["bm25"] for r in vector_results), default=1.0)
        if max_bm25 > 0:
            for r in vector_results:
                r["bm25_norm"] = r["bm25"] / max_bm25
        else:
            for r in vector_results:
                r["bm25_norm"] = 0.0

        # 5) Helpfulness scoring
        helpfulness_map = _load_helpfulness_map(root) if helpfulness_weight > 0 else {}

        # 6) Compute combined scores
        for r in vector_results:
            fp = r["file_path"]
            f_score = freshness_cache.get(fp, 0.0)
            h_score = helpfulness_map.get(fp, 0.0)
            r["freshness"] = f_score
            r["helpfulness"] = h_score
            r["combined"] = (
                vector_weight * r["similarity"]
                + bm25_weight * r["bm25_norm"]
                + freshness_weight * f_score
                + helpfulness_weight * h_score
            )

        # Sort by combined score
        vector_results.sort(key=lambda x: x["combined"], reverse=True)

        # Deduplicate by file (keep best chunk per file)
        seen_files: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for r in vector_results:
            if r["file_path"] not in seen_files:
                seen_files.add(r["file_path"])
                deduped.append(r)
            if len(deduped) >= limit:
                break

        # Format output
        lines: list[str] = [f"**Semantic search:** {query}", ""]
        for i, r in enumerate(deduped, 1):
            heading_str = f" § {r['heading']}" if r.get("heading") else ""
            lines.append(f"**{i}. {r['file_path']}**{heading_str}")
            lines.append(
                f"  _combined: {r['combined']:.3f} "
                f"(vector: {r['similarity']:.3f}, "
                f"bm25: {r['bm25_norm']:.3f}, "
                f"freshness: {r['freshness']:.3f}, "
                f"helpfulness: {r['helpfulness']:.3f})_"
            )
            # Show a content preview (first 200 chars)
            preview = r["content"][:200].replace("\n", " ")
            if len(r["content"]) > 200:
                preview += "…"
            lines.append(f"  {preview}")
            lines.append("")

        if not deduped:
            return f"No results found for: {query}"

        lines.append(f"_Showing {len(deduped)} of {index.chunk_count()} indexed chunks._")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # memory_reindex
    # ------------------------------------------------------------------

    @mcp.tool(
        name="memory_reindex",
        annotations=_tool_annotations(
            title="Rebuild Semantic Search Index",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_reindex(force: bool = False) -> str:
        """Rebuild the semantic search embedding index.

        Scans knowledge, skills, and users directories for .md files,
        chunks them, and embeds each chunk. By default only re-indexes
        files that have changed since last index; set ``force=True`` to
        re-embed everything.

        Requires ``sentence-transformers``.

        Call ``memory_tool_schema`` with ``"memory_reindex"`` for the
        incremental-versus-full rebuild contract.

        Args:
            force: Re-index all files regardless of modification time.
        """
        if not _check_embedding_deps():
            return (
                "⚠️ sentence-transformers is not installed. "
                "Install with: pip install agent-memory-mcp[search]"
            )

        index = _get_index()
        stats = index.build_index(force=force)
        total = index.chunk_count()

        return (
            f"Reindex complete. "
            f"Indexed: {stats['indexed']}, "
            f"Skipped (unchanged): {stats['skipped']}, "
            f"Removed (deleted): {stats['removed']}, "
            f"Errors: {stats['errors']}. "
            f"Total chunks: {total}."
        )

    return {
        "memory_semantic_search": memory_semantic_search,
        "memory_reindex": memory_reindex,
    }
