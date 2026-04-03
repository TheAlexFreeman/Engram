"""Implementation of the ``engram search`` subcommand."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..git_repo import GitRepo

_IGNORED_NAMES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
)
_DEFAULT_SCOPES = (
    "memory/knowledge",
    "memory/skills",
    "memory/users",
    "memory/working/projects",
)


@dataclass(frozen=True, slots=True)
class SearchResult:
    path: str
    trust: str | None
    snippet: str
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "trust": self.trust,
            "snippet": self.snippet,
        }
        if self.score is not None:
            payload["score"] = round(self.score, 6)
        return payload


def register_search(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "search",
        help="Search memory content from the terminal.",
        parents=parents or [],
    )
    parser.add_argument("query", nargs="+", help="Search query.")
    parser.add_argument(
        "--scope",
        help="Restrict search to a repo-relative folder such as memory/knowledge.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to return.",
    )
    parser.add_argument(
        "--keyword",
        action="store_true",
        help="Force keyword search even when semantic search dependencies are installed.",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching for keyword search.",
    )
    parser.set_defaults(handler=run_search)
    return parser


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_scalar_frontmatter(path: Path) -> dict[str, str]:
    text = _read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""


def _try_git_repo(repo_root: Path, content_root: Path) -> GitRepo | None:
    try:
        return GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
    except Exception:
        return None


def _resolve_scope(
    repo_root: Path, content_root: Path, raw_scope: str | None
) -> tuple[str | None, Path]:
    if not raw_scope or raw_scope.strip() in {"", "."}:
        default_root = content_root / "memory"
        return None, default_root if default_root.exists() else content_root

    normalized = raw_scope.replace("\\", "/").strip().rstrip("/")
    alias_map = {
        "knowledge": "memory/knowledge",
        "users": "memory/users",
        "skills": "memory/skills",
        "plans": "memory/working/projects",
    }
    normalized = alias_map.get(normalized, normalized)
    candidate = Path(normalized)
    if candidate.is_absolute():
        return normalized, candidate.resolve()
    if normalized.startswith("HUMANS/"):
        return normalized, (repo_root / normalized).resolve()
    return normalized, (content_root / normalized).resolve()


def _iter_markdown_files(scope_path: Path) -> list[Path]:
    if scope_path.is_file():
        return [scope_path] if scope_path.suffix == ".md" else []

    if not scope_path.exists():
        return []

    files: list[Path] = []
    for path in sorted(scope_path.rglob("*.md")):
        if any(part in _IGNORED_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _format_snippet(text: str, *, limit: int = 200) -> str:
    snippet = " ".join(text.strip().split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 1].rstrip() + "…"


def _keyword_search(
    repo_root: Path,
    content_root: Path,
    query: str,
    *,
    scope: str | None,
    scope_path: Path,
    limit: int,
    case_sensitive: bool,
) -> list[SearchResult]:
    pattern = re.compile(re.escape(query), 0 if case_sensitive else re.IGNORECASE)
    git_repo = _try_git_repo(repo_root, content_root)
    seen_files: set[str] = set()
    results: list[SearchResult] = []

    if git_repo is not None and scope_path.exists():
        try:
            relative_scope = scope or "memory"
            if scope_path.is_file():
                git_glob = relative_scope
            elif relative_scope:
                git_glob = f"{relative_scope}/**/*.md"
            else:
                git_glob = "memory/**/*.md"

            for file_rel, _line_no, line_text in git_repo.grep(
                re.escape(query),
                glob=git_glob,
                case_sensitive=case_sensitive,
            ):
                if len(results) >= limit or file_rel in seen_files:
                    continue
                seen_files.add(file_rel)
                metadata = _parse_scalar_frontmatter(content_root / file_rel)
                results.append(
                    SearchResult(
                        path=file_rel,
                        trust=metadata.get("trust"),
                        snippet=_format_snippet(line_text),
                    )
                )
        except Exception:
            pass

    for path in _iter_markdown_files(scope_path):
        if len(results) >= limit:
            break
        try:
            rel_path = path.relative_to(content_root).as_posix()
        except ValueError:
            rel_path = path.relative_to(repo_root).as_posix()
        if rel_path in seen_files:
            continue
        text = _read_text(path)
        first_match = next((line for line in text.splitlines() if pattern.search(line)), None)
        if first_match is None:
            continue
        seen_files.add(rel_path)
        metadata = _parse_scalar_frontmatter(path)
        results.append(
            SearchResult(
                path=rel_path,
                trust=metadata.get("trust"),
                snippet=_format_snippet(first_match),
            )
        )

    return results[:limit]


def _semantic_available() -> bool:
    try:
        from ..tools.semantic.search_tools import _check_embedding_deps
    except ModuleNotFoundError:
        return False
    return bool(_check_embedding_deps())


def _semantic_search(
    repo_root: Path,
    content_root: Path,
    query: str,
    *,
    scope: str | None,
    scope_path: Path,
    limit: int,
) -> list[SearchResult]:
    from ..tools.semantic.search_tools import EmbeddingIndex

    index = EmbeddingIndex(repo_root, content_root)
    scope_prefix: str | None = scope
    scopes = [scope_prefix] if scope_prefix else list(_DEFAULT_SCOPES)
    target_file: str | None = None

    if scope_prefix and scope_path.is_file():
        target_file = scope_prefix
        scope_prefix = str(Path(scope_prefix).parent).replace("\\", "/")
        scopes = [scope_prefix]

    index.build_index(scopes=scopes)
    raw_results = index.search_vectors(query, limit=max(limit * 5, limit), scope=scope_prefix)

    deduped: list[SearchResult] = []
    seen_files: set[str] = set()
    for item in raw_results:
        file_path = str(item["file_path"])
        if target_file is not None and file_path != target_file:
            continue
        if file_path in seen_files:
            continue
        seen_files.add(file_path)
        metadata = _parse_scalar_frontmatter(content_root / file_path)
        deduped.append(
            SearchResult(
                path=file_path,
                trust=metadata.get("trust"),
                snippet=_format_snippet(str(item["content"])),
                score=float(item["similarity"]),
            )
        )
        if len(deduped) >= limit:
            break

    return deduped


def _render_human(mode: str, results: list[SearchResult], fallback_note: str | None) -> str:
    banner = f"Mode: {mode}"
    if fallback_note:
        banner = f"{banner} ({fallback_note})"

    if not results:
        return banner + "\n\nNo results found."

    lines = [banner, ""]
    for index, item in enumerate(results, start=1):
        trust_suffix = f" [{item.trust}]" if item.trust else ""
        header = f"{index}. {item.path}{trust_suffix}"
        if item.score is not None:
            header = f"{header} ({item.score:.3f})"
        lines.append(header)
        lines.append(f"   {item.snippet}")
    return "\n".join(lines)


def run_search(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    query = " ".join(args.query).strip()
    if not query:
        raise ValueError("query must not be empty")

    limit = max(int(args.limit), 1)
    scope, scope_path = _resolve_scope(repo_root, content_root, args.scope)
    if not scope_path.exists():
        raise ValueError(f"Scope not found: {args.scope}")

    mode = "keyword"
    fallback_note: str | None = None
    if not args.keyword and scope_path.is_relative_to(content_root) and _semantic_available():
        mode = "semantic"
        results = _semantic_search(
            repo_root,
            content_root,
            query,
            scope=scope,
            scope_path=scope_path,
            limit=limit,
        )
    else:
        if not args.keyword and not _semantic_available():
            fallback_note = "sentence-transformers unavailable"
        elif args.keyword:
            fallback_note = "forced by --keyword"
        results = _keyword_search(
            repo_root,
            content_root,
            query,
            scope=scope,
            scope_path=scope_path,
            limit=limit,
            case_sensitive=bool(args.case_sensitive),
        )

    payload = {
        "mode": mode,
        "query": query,
        "scope": scope,
        "results": [item.to_dict() for item in results],
    }
    if fallback_note:
        payload["note"] = fallback_note

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_render_human(mode, results, fallback_note))
    return 0
