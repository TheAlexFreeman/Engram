"""Implementation of the ``engram recall`` subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import cmd_search
from .formatting import (
    age_days,
    build_access_index,
    format_snippet,
    iter_markdown_files,
    load_access_entries,
    read_markdown,
    relativize_path,
    resolve_target_path,
)


def register_recall(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "recall",
        help="Inspect a memory file or namespace with frontmatter and ACCESS context.",
        parents=parents or [],
    )
    parser.add_argument("target", nargs="+", help="Repo-relative path, namespace alias, or query.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum namespace entries or query candidates to include.",
    )
    parser.add_argument(
        "--keyword",
        action="store_true",
        help="Force keyword matching when falling back to query search.",
    )
    parser.set_defaults(handler=run_recall)
    return parser


def _search_candidates(
    query: str,
    *,
    repo_root: Path,
    content_root: Path,
    limit: int,
    keyword: bool,
) -> tuple[str, list[cmd_search.SearchResult], str | None]:
    scope_path = content_root / "memory"
    if not scope_path.exists():
        scope_path = content_root

    mode = "keyword"
    fallback_note: str | None = None
    if not keyword and scope_path.is_relative_to(content_root) and cmd_search._semantic_available():
        mode = "semantic"
        results = cmd_search._semantic_search(
            repo_root,
            content_root,
            query,
            scope=None,
            scope_path=scope_path,
            limit=limit,
        )
    else:
        if not keyword and not cmd_search._semantic_available():
            fallback_note = "sentence-transformers unavailable"
        elif keyword:
            fallback_note = "forced by --keyword"
        results = cmd_search._keyword_search(
            repo_root,
            content_root,
            query,
            scope=None,
            scope_path=scope_path,
            limit=limit,
            case_sensitive=False,
        )
    return mode, results, fallback_note


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_file_payload(
    path: Path,
    *,
    repo_root: Path,
    content_root: Path,
    access_index: dict[str, dict[str, Any]],
    resolved_from: str,
    query: str | None = None,
    query_mode: str | None = None,
    query_note: str | None = None,
    query_matches: list[cmd_search.SearchResult] | None = None,
) -> dict[str, Any]:
    rel_path = relativize_path(path, repo_root=repo_root, content_root=content_root)
    frontmatter, body = read_markdown(path)
    access_summary = access_index.get(rel_path, {"count": 0, "last_date": None})
    payload: dict[str, Any] = {
        "kind": "file",
        "path": rel_path,
        "resolved_from": resolved_from,
        "frontmatter": frontmatter or None,
        "verification": {
            "created": _stringify(frontmatter.get("created")),
            "last_verified": _stringify(frontmatter.get("last_verified")),
            "age_days": age_days(frontmatter),
        },
        "access": {
            "count": int(access_summary.get("count", 0)),
            "last_date": access_summary.get("last_date"),
        },
        "content": body,
    }
    if query is not None:
        payload["query"] = query
    if query_mode is not None:
        payload["query_mode"] = query_mode
    if query_note is not None:
        payload["query_note"] = query_note
    if query_matches:
        payload["query_matches"] = [item.to_dict() for item in query_matches]
    return payload


def _build_namespace_payload(
    path: Path,
    *,
    repo_root: Path,
    content_root: Path,
    access_index: dict[str, dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    rel_path = relativize_path(path, repo_root=repo_root, content_root=content_root)
    summary_path = path / "SUMMARY.md"
    summary_payload: dict[str, Any] | None = None
    if summary_path.exists():
        summary_frontmatter, summary_body = read_markdown(summary_path)
        summary_payload = {
            "path": relativize_path(summary_path, repo_root=repo_root, content_root=content_root),
            "frontmatter": summary_frontmatter or None,
            "content": summary_body,
        }

    entries: list[dict[str, Any]] = []
    all_files = iter_markdown_files(path, include_summary=False)
    for entry_path in all_files[:limit]:
        file_frontmatter, body = read_markdown(entry_path)
        file_rel_path = relativize_path(entry_path, repo_root=repo_root, content_root=content_root)
        access_summary = access_index.get(file_rel_path, {"count": 0, "last_date": None})
        entries.append(
            {
                "path": file_rel_path,
                "trust": _stringify(file_frontmatter.get("trust")),
                "source": _stringify(file_frontmatter.get("source")),
                "created": _stringify(file_frontmatter.get("created")),
                "last_verified": _stringify(file_frontmatter.get("last_verified")),
                "age_days": age_days(file_frontmatter),
                "access_count": int(access_summary.get("count", 0)),
                "last_accessed": access_summary.get("last_date"),
                "snippet": format_snippet(body, limit=160),
            }
        )

    return {
        "kind": "namespace",
        "path": rel_path,
        "resolved_from": "path",
        "summary": summary_payload,
        "total_entries": len(all_files),
        "entries": entries,
        "limit": limit,
    }


def _render_recall(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    if payload.get("resolved_from") == "query":
        lines.append(f"Matched by query: {payload['query']}")
        lines.append(f"Match mode: {payload.get('query_mode', 'keyword')}")
        if payload.get("query_note"):
            lines.append(f"Match note: {payload['query_note']}")
        lines.append("")

    if payload["kind"] == "file":
        frontmatter = payload.get("frontmatter") or {}
        verification = payload.get("verification") or {}
        access = payload.get("access") or {}
        lines.append(f"Path: {payload['path']}")
        if frontmatter.get("trust"):
            lines.append(f"Trust: {frontmatter['trust']}")
        if frontmatter.get("source"):
            lines.append(f"Source: {frontmatter['source']}")
        if frontmatter.get("origin_session"):
            lines.append(f"Origin session: {frontmatter['origin_session']}")
        if verification.get("created"):
            lines.append(f"Created: {verification['created']}")
        if verification.get("last_verified"):
            lines.append(f"Last verified: {verification['last_verified']}")
        if verification.get("age_days") is not None:
            lines.append(f"Age: {verification['age_days']} days")
        lines.append(f"Accesses: {access.get('count', 0)}")
        if access.get("last_date"):
            lines.append(f"Last accessed: {access['last_date']}")
        lines.append("")
        body = (payload.get("content") or "").rstrip()
        lines.append(body or "_(empty file)_")

        query_matches = payload.get("query_matches") or []
        if len(query_matches) > 1:
            lines.append("")
            lines.append("Other candidates:")
            for item in query_matches[1:4]:
                trust_suffix = f" [{item['trust']}]" if item.get("trust") else ""
                lines.append(f"  - {item['path']}{trust_suffix}")
    else:
        lines.append(f"Namespace: {payload['path']}")
        lines.append(f"Files: {payload['total_entries']}")
        summary = payload.get("summary")
        if summary is not None:
            lines.append("")
            lines.append("Summary:")
            lines.append((summary.get("content") or "").rstrip() or "_(empty summary)_")
        if payload.get("entries"):
            lines.append("")
            lines.append(f"Entries (showing up to {payload['limit']}):")
            for index, item in enumerate(payload["entries"], start=1):
                trust_suffix = f" [{item['trust']}]" if item.get("trust") else ""
                lines.append(f"{index}. {item['path']}{trust_suffix}")
                detail_parts: list[str] = []
                if item.get("source"):
                    detail_parts.append(f"source: {item['source']}")
                if item.get("created"):
                    detail_parts.append(f"created: {item['created']}")
                if item.get("access_count") is not None:
                    detail_parts.append(f"accesses: {item['access_count']}")
                if detail_parts:
                    lines.append(f"   {' | '.join(detail_parts)}")
                if item.get("snippet"):
                    lines.append(f"   {item['snippet']}")
        else:
            lines.append("")
            lines.append("No markdown files found in this namespace.")

    return "\n".join(lines)


def run_recall(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    raw_target = " ".join(args.target).strip()
    if not raw_target:
        raise ValueError("target must not be empty")

    limit = max(int(args.limit), 1)
    access_entries = load_access_entries(content_root)
    access_index = build_access_index(access_entries)
    target_path = resolve_target_path(repo_root, content_root, raw_target)

    if target_path is None:
        mode, matches, note = _search_candidates(
            raw_target,
            repo_root=repo_root,
            content_root=content_root,
            limit=limit,
            keyword=bool(args.keyword),
        )
        if not matches:
            payload = {"kind": None, "query": raw_target, "matches": []}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f'No file, namespace, or query match found for "{raw_target}".')
            return 1

        resolved_match = resolve_target_path(repo_root, content_root, matches[0].path)
        if resolved_match is None:
            raise ValueError(f"Matched path is not readable: {matches[0].path}")
        payload = _build_file_payload(
            resolved_match,
            repo_root=repo_root,
            content_root=content_root,
            access_index=access_index,
            resolved_from="query",
            query=raw_target,
            query_mode=mode,
            query_note=note,
            query_matches=matches,
        )
    elif target_path.is_dir():
        payload = _build_namespace_payload(
            target_path,
            repo_root=repo_root,
            content_root=content_root,
            access_index=access_index,
            limit=limit,
        )
    else:
        payload = _build_file_payload(
            target_path,
            repo_root=repo_root,
            content_root=content_root,
            access_index=access_index,
            resolved_from="path",
        )

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_recall(payload))
    return 0
