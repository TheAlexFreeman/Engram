"""Read tools — links submodule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...response_envelope import dump_tool_result
from ..reference_extractor import (
    build_connectivity_graph,
    diff_connectivity_graphs,
    find_references,
    find_unlinked_files,
    preview_reorganization,
    resolve_link_diagnostics,
    score_existing_links,
    suggest_links_for_file,
    suggest_structure,
    summarize_cross_domain_links,
    validate_links,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


def register_links(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    *,
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register links read tools and return their callables."""
    _filter_link_delta_payload = H._filter_link_delta_payload
    _git_snapshot_graph = H._git_snapshot_graph
    _iter_markdown_links = H._iter_markdown_links
    _list_tracked_markdown_files = H._list_tracked_markdown_files
    _resolve_repo_relative_target = H._resolve_repo_relative_target
    _resolve_visible_path = H._resolve_visible_path
    _tool_annotations = H._tool_annotations

    def _dump_payload(payload: Any) -> str:
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(payload, session_state, indent=2)

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_resolve_link",
        annotations=_tool_annotations(
            title="Resolve Link Target",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_resolve_link(path: str, target: str) -> str:
        """Resolve one markdown-style target relative to a governed source path."""
        from ...errors import NotFoundError, ValidationError

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")
        if not isinstance(target, str) or not target.strip():
            raise ValidationError("target must be a non-empty string")

        root = get_root()
        source_path = _resolve_visible_path(root, path.strip())
        try:
            source_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not source_path.exists() or not source_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        rel_path = source_path.relative_to(root).as_posix()
        payload = resolve_link_diagnostics(root, rel_path, target)
        if session_state is not None:
            session_state.record_read(rel_path)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_find_references

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_find_references",
        annotations=_tool_annotations(
            title="Find Path References",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_find_references(path: str, include_body: bool = False) -> str:
        """Return structured references to a path or path fragment across governed markdown."""
        from ...errors import ValidationError

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")

        root = get_root()
        matches = find_references(root, path.strip(), include_body=include_body)
        payload = {
            "query": path.strip(),
            "include_body": include_body,
            "matches": matches,
            "total": len(matches),
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_validate_links

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_validate_links",
        annotations=_tool_annotations(
            title="Validate Internal Links",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_validate_links(path: str = "") -> str:
        """Validate internal markdown and frontmatter path references within governed content."""
        from ...errors import ValidationError

        root = get_root()
        requested_path = path.strip().replace("\\", "/")
        if requested_path:
            scope_path = _resolve_visible_path(root, requested_path)
            try:
                scope_path.relative_to(root)
            except ValueError as exc:
                raise ValidationError("path must stay within the repository root") from exc
            if not scope_path.exists():
                return f"Error: Path not found: {path}"

        payload = validate_links(root, requested_path)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_reorganize_preview

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_reorganize_preview",
        annotations=_tool_annotations(
            title="Preview Path Reorganization",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_reorganize_preview(source: str, dest: str) -> str:
        """Preview the impact of moving a file or subtree to a new repository path."""
        from ...errors import ValidationError

        if not isinstance(source, str) or not source.strip():
            raise ValidationError("source must be a non-empty string")
        if not isinstance(dest, str) or not dest.strip():
            raise ValidationError("dest must be a non-empty string")

        root = get_root()
        normalized_source = source.strip().replace("\\", "/").strip("/")
        normalized_dest = dest.strip().replace("\\", "/").strip("/")
        source_path = (root / normalized_source).resolve()
        dest_path = (root / normalized_dest).resolve()

        try:
            source_path.relative_to(root)
            dest_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("source and dest must stay within the repository root") from exc

        if not source_path.exists():
            return f"Error: Path not found: {source}"

        dest_parent = dest_path.parent
        if not dest_parent.exists():
            raise ValidationError(
                f"destination parent does not exist: {dest_parent.relative_to(root).as_posix()}"
            )

        payload = preview_reorganization(root, normalized_source, normalized_dest)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_suggest_structure

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_suggest_structure",
        annotations=_tool_annotations(
            title="Suggest Structure Improvements",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_suggest_structure(
        folder_path: str = "",
        heuristics: list[str] | None = None,
    ) -> str:
        """Suggest advisory structure improvements for the governed markdown tree."""
        from ...errors import ValidationError

        root = get_root()
        requested_path = folder_path.strip().replace("\\", "/")
        if requested_path:
            scope_path = _resolve_visible_path(root, requested_path)
            try:
                scope_path.relative_to(root)
            except ValueError as exc:
                raise ValidationError("folder_path must stay within the repository root") from exc
            if not scope_path.exists():
                return f"Error: Path not found: {folder_path}"

        if heuristics is not None:
            if not isinstance(heuristics, list) or not all(
                isinstance(item, str) for item in heuristics
            ):
                raise ValidationError("heuristics must be a list of strings")

        try:
            payload = suggest_structure(root, requested_path, heuristics)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_check_cross_references

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_suggest_links",
        annotations=_tool_annotations(
            title="Suggest Cross References",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_suggest_links(
        path: str,
        max_suggestions: int = 10,
        domain_mode: str = "all",
        min_score: float = 0.0,
    ) -> str:
        """Return scored cross-reference suggestions for one governed markdown file."""
        from ...errors import NotFoundError, ValidationError

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")
        max_suggestions = max(1, min(max_suggestions, 25))
        if not isinstance(domain_mode, str) or not domain_mode.strip():
            raise ValidationError("domain_mode must be a non-empty string")
        if not isinstance(min_score, (int, float)):
            raise ValidationError("min_score must be numeric")

        root = get_root()
        target_path = _resolve_visible_path(root, path.strip())
        try:
            target_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not target_path.exists() or not target_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        rel_path = target_path.relative_to(root).as_posix()
        try:
            payload = suggest_links_for_file(
                root,
                rel_path,
                max_suggestions=max_suggestions,
                domain_mode=domain_mode,
                min_score=float(min_score),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if session_state is not None:
            session_state.record_read(rel_path)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_score_existing_links

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_score_existing_links",
        annotations=_tool_annotations(
            title="Score Existing Links",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_score_existing_links(
        path: str,
        scope: str = "",
        min_score: float = 1.0,
        domain_mode: str = "all",
    ) -> str:
        """Score each outgoing link from a file to identify weak pruning candidates.

        Uses the same structural heuristics as ``memory_suggest_links`` (stem
        overlap, shared directory, co-citation, body mentions) but applied to
        *existing* links rather than uncreated candidates.  Links scoring below
        *min_score* are flagged as ``alert=true``.

        Args:
            path: Repo-relative path to the file to audit (e.g.
                  ``"memory/knowledge/ai/alignment.md"``).
            scope: Unused — reserved for future batch-mode support.
            min_score: Links below this score are flagged as pruning candidates
                  (default 1.0, which is below the "same domain only" baseline).
            domain_mode: ``"all"`` (default) — score all outgoing links;
                  ``"same"`` — only same-domain links; ``"cross"`` — only
                  cross-domain links.
        """
        from ...errors import NotFoundError, ValidationError

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")
        if not isinstance(min_score, (int, float)):
            raise ValidationError("min_score must be numeric")
        normalized_domain_mode = (domain_mode or "all").strip().lower()
        if normalized_domain_mode not in {"all", "same", "cross"}:
            raise ValidationError("domain_mode must be one of: all, same, cross")

        root = get_root()
        target_path = _resolve_visible_path(root, path.strip())
        try:
            target_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not target_path.exists() or not target_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        rel_path = target_path.relative_to(root).as_posix()
        graph = build_connectivity_graph(root)
        if rel_path not in graph.outgoing:
            raise ValidationError(f"File is outside the governed markdown surface: {rel_path}")

        min_score_f = max(0.0, float(min_score))
        all_scored = score_existing_links(rel_path, graph, root, min_score=min_score_f)

        # Apply domain_mode filter
        source_parts = Path(rel_path).parts
        source_domain = source_parts[2] if len(source_parts) > 2 else ""
        filtered: list[dict] = []
        for entry in all_scored:
            tgt_parts = Path(entry["target"]).parts
            tgt_domain = tgt_parts[2] if len(tgt_parts) > 2 else ""
            is_same = bool(source_domain and tgt_domain and source_domain == tgt_domain)
            if normalized_domain_mode == "same" and not is_same:
                continue
            if normalized_domain_mode == "cross" and is_same:
                continue
            filtered.append({**entry, "is_same_domain": is_same})

        pruning_candidates = [e for e in filtered if e["alert"]]
        strong_links = [e for e in filtered if not e["alert"]]

        payload = {
            "path": rel_path,
            "min_score": round(min_score_f, 2),
            "domain_mode": normalized_domain_mode,
            "total_links": len(filtered),
            "pruning_candidates": pruning_candidates,
            "strong_links": strong_links,
            "in_degree": len(graph.incoming.get(rel_path, set())),
            "out_degree": len(graph.outgoing.get(rel_path, set())),
        }
        if session_state is not None:
            session_state.record_read(rel_path)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_score_links_by_access

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_score_links_by_access",
        annotations=_tool_annotations(
            title="Score Links by Access Co-occurrence",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_score_links_by_access(
        path: str,
        lookback_days: int = 90,
        min_access_score: int = 1,
    ) -> str:
        """Score each outgoing link by how often the two files are read together.

        Parses ACCESS.jsonl logs across all governed scopes.  Within each
        session (grouped by ``session_id`` or date), every pair of files
        accessed contributes +1 to their co-access count.  Links whose files
        are never read in the same session score 0 and are flagged as
        ``never_co_accessed``.

        Args:
            path: Repo-relative path to the file to audit.
            lookback_days: Only consider ACCESS entries within this window
                  (default 90 days).
            min_access_score: Links with fewer co-accesses than this are
                  flagged as pruning candidates (default 1 — flags all
                  zero-co-access links).
        """
        from ...errors import NotFoundError, ValidationError
        from ..graph_analysis import parse_co_access
        from ..graph_analysis import score_links_by_access as _slba

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")
        lookback = max(1, int(lookback_days))
        min_score = max(0, int(min_access_score))

        root = get_root()
        target_path = _resolve_visible_path(root, path.strip())
        try:
            target_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not target_path.exists() or not target_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        rel_path = target_path.relative_to(root).as_posix()
        graph = build_connectivity_graph(root)
        if rel_path not in graph.outgoing:
            raise ValidationError(f"File is outside the governed markdown surface: {rel_path}")

        co_access = parse_co_access(root, lookback_days=lookback)
        all_scored = _slba(rel_path, co_access, graph)

        pruning_candidates = [e for e in all_scored if e["access_score"] < min_score]
        strong_links = [e for e in all_scored if e["access_score"] >= min_score]

        payload = {
            "path": rel_path,
            "lookback_days": lookback,
            "min_access_score": min_score,
            "total_links": len(all_scored),
            "pruning_candidates": pruning_candidates,
            "strong_links": strong_links,
            "out_degree": len(graph.outgoing.get(rel_path, set())),
        }
        if session_state is not None:
            session_state.record_read(rel_path)
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_check_cross_references

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_cross_references",
        annotations=_tool_annotations(
            title="Check Cross References",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_cross_references(
        path: str = ".",
        check_summaries: bool = True,
        check_links: bool = True,
    ) -> str:
        """Scan tracked Markdown files for broken links and SUMMARY drift.

        Uses git ls-files to enumerate tracked Markdown files within the
        requested scope, then checks relative Markdown links and SUMMARY.md
        coverage. External URLs and anchor-only links are ignored.

        Args:
            path: Repo-relative file or folder scope to scan (default: '.').
            check_summaries: Report SUMMARY.md orphan and stale entries.
            check_links: Report broken relative Markdown links.

        Returns:
            Structured JSON describing broken links, orphaned files, stale
            summary entries, and scan statistics.
        """
        from ...errors import ValidationError

        root = get_root()
        requested_path = path.strip() or "."
        scope_path = _resolve_visible_path(root, requested_path)
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc

        if not scope_path.exists():
            return f"Error: Path not found: {path}"

        scope = scope_path.relative_to(root).as_posix() if scope_path != root else "."
        tracked_files = _list_tracked_markdown_files(root, scope)
        if len(tracked_files) > 500:
            raise ValidationError(
                "memory_check_cross_references scans at most 500 tracked Markdown files; narrow path"
            )

        broken_links: list[dict[str, Any]] = []
        orphaned_files: list[dict[str, Any]] = []
        stale_summary_entries: list[dict[str, Any]] = []
        links_checked = 0

        file_groups: dict[Path, list[Path]] = {}
        summary_paths: list[Path] = []

        for abs_path in tracked_files:
            file_groups.setdefault(abs_path.parent, []).append(abs_path)
            if abs_path.name == "SUMMARY.md":
                summary_paths.append(abs_path)

            text = abs_path.read_text(encoding="utf-8")
            if not check_links:
                continue

            for line_no, target in _iter_markdown_links(text):
                resolved_target, reason = _resolve_repo_relative_target(root, abs_path, target)
                links_checked += 1
                if reason is None:
                    continue
                broken_links.append(
                    {
                        "file": abs_path.relative_to(root).as_posix(),
                        "line": line_no,
                        "target": resolved_target or target,
                        "reason": reason,
                    }
                )
                if check_summaries and abs_path.name == "SUMMARY.md":
                    stale_summary_entries.append(
                        {
                            "summary": abs_path.relative_to(root).as_posix(),
                            "entry": target,
                            "reason": reason,
                        }
                    )

        if check_summaries:
            for summary_path in summary_paths:
                summary_rel = summary_path.relative_to(root).as_posix()
                summary_text = summary_path.read_text(encoding="utf-8")
                linked_targets: set[str] = set()
                for _, target in _iter_markdown_links(summary_text):
                    resolved_target, reason = _resolve_repo_relative_target(
                        root, summary_path, target
                    )
                    if resolved_target is not None:
                        linked_targets.add(resolved_target)
                    if reason is not None and not any(
                        item["summary"] == summary_rel and item["entry"] == target
                        for item in stale_summary_entries
                    ):
                        stale_summary_entries.append(
                            {
                                "summary": summary_rel,
                                "entry": target,
                                "reason": reason,
                            }
                        )

                for sibling in sorted(file_groups.get(summary_path.parent, [])):
                    if sibling.name == "SUMMARY.md":
                        continue
                    sibling_rel = sibling.relative_to(root).as_posix()
                    if sibling_rel in linked_targets or sibling.name in summary_text:
                        continue
                    orphaned_files.append(
                        {
                            "file": sibling_rel,
                            "folder_summary": summary_rel,
                            "reason": "not mentioned in SUMMARY.md",
                        }
                    )

        result = {
            "broken_links": broken_links,
            "orphaned_files": orphaned_files,
            "stale_summary_entries": stale_summary_entries,
            "stats": {
                "files_scanned": len(tracked_files),
                "links_checked": links_checked,
                "summaries_checked": len(summary_paths) if check_summaries else 0,
                "issues_found": (
                    len(broken_links) + len(orphaned_files) + len(stale_summary_entries)
                ),
            },
        }
        return _dump_payload(result)

    # ------------------------------------------------------------------
    # memory_surface_unlinked

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_cross_domain_links",
        annotations=_tool_annotations(
            title="Summarize Cross-Domain Links",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_cross_domain_links(
        path: str = "memory/knowledge",
        source_domain: str = "",
        target_domain: str = "",
        min_edge_count: int = 1,
    ) -> str:
        """Summarize cross-domain link flow within the knowledge graph."""
        from ...errors import ValidationError

        root = get_root()
        requested_path = path.strip().replace("\\", "/") or "memory/knowledge"
        if not isinstance(min_edge_count, int):
            raise ValidationError("min_edge_count must be an integer")
        scope_path = _resolve_visible_path(root, requested_path)
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not scope_path.exists():
            return f"Error: Path not found: {path}"

        payload = summarize_cross_domain_links(
            root,
            requested_path,
            source_domain=source_domain,
            target_domain=target_domain,
            min_edge_count=min_edge_count,
        )
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_surface_unlinked

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_surface_unlinked",
        annotations=_tool_annotations(
            title="Surface Unlinked Files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_surface_unlinked(
        scope: str = "memory/knowledge",
        max_results: int = 25,
        include_suggestions: bool = True,
        threshold: int = 2,
        category: str = "",
    ) -> str:
        """Surface knowledge files with zero or low cross-reference connectivity.

        Builds a lightweight in-degree/out-degree connectivity graph of the
        governed Markdown files in the requested scope, identifies files that
        are isolated, sinks, sources, or have low total connectivity, and
        returns a prioritised review queue with enough context for an agent to
        decide what links to add.

        Use this tool to discover files that would benefit from additional
        cross-references. After reviewing the results, use the existing
        write tools (e.g. memory_update_frontmatter) to add ``related:``
        entries or inline Markdown links.

        Args:
            scope: Repo-relative folder to scan (default: 'memory/knowledge').
            max_results: Maximum candidates to return (default: 25, max: 100).
            include_suggestions: Include heuristic link suggestions per candidate.
            threshold: Total-degree ceiling for 'low_connectivity' bucket (default: 2).
            category: Filter to a single category: 'isolated', 'sink', 'source',
                      'low_connectivity', or '' for all.

        Returns:
            Structured JSON with graph statistics, prioritised candidate list,
            and optional link suggestions per candidate.
        """
        from ...errors import ValidationError

        root = get_root()
        requested_scope = scope.strip().replace("\\", "/")
        if not requested_scope:
            requested_scope = "memory/knowledge"

        scope_path = (root / requested_scope).resolve()
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("scope must stay within the repository root") from exc
        if not scope_path.exists():
            return f"Error: Path not found: {scope}"

        max_results = max(1, min(max_results, 100))
        if threshold < 0:
            raise ValidationError("threshold must be non-negative")

        valid_categories = {"", "isolated", "sink", "source", "low_connectivity"}
        if category not in valid_categories:
            raise ValidationError(
                f"category must be one of {sorted(valid_categories - {''})!r} or '' for all"
            )

        try:
            payload = find_unlinked_files(
                root=root,
                scope=requested_scope,
                threshold=threshold,
                category_filter=category,
                max_results=max_results,
                include_suggestions=include_suggestions,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_link_delta

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_link_delta",
        annotations=_tool_annotations(
            title="Diff Link Surface",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_link_delta(
        path: str = "memory/knowledge",
        base_ref: str = "HEAD",
        cross_domain_only: bool = False,
        transition_filter: str = "",
    ) -> str:
        """Diff the current connectivity graph against a git base revision."""
        from ...errors import ValidationError

        if not isinstance(base_ref, str) or not base_ref.strip():
            raise ValidationError("base_ref must be a non-empty string")

        root = get_root()
        requested_path = path.strip().replace("\\", "/") or "memory/knowledge"
        scope_path = _resolve_visible_path(root, requested_path)
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not scope_path.exists():
            return f"Error: Path not found: {path}"

        repo = get_repo()
        current_graph = build_connectivity_graph(root, requested_path)
        previous_graph = _git_snapshot_graph(repo, requested_path, base_ref.strip())
        payload = diff_connectivity_graphs(current_graph, previous_graph)
        payload["scope"] = requested_path
        payload["base_ref"] = base_ref.strip()
        payload["cross_domain_only"] = cross_domain_only
        payload["transition_filter"] = transition_filter.strip()
        payload = _filter_link_delta_payload(
            payload,
            cross_domain_only=cross_domain_only,
            transition_filter=transition_filter,
        )
        if len(payload["added_edges"]) > 200:
            payload["added_edges"] = payload["added_edges"][:200]
            payload["added_edges_truncated"] = True
        if len(payload["removed_edges"]) > 200:
            payload["removed_edges"] = payload["removed_edges"][:200]
            payload["removed_edges_truncated"] = True
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_generate_summary

    return {
        "memory_resolve_link": memory_resolve_link,
        "memory_find_references": memory_find_references,
        "memory_validate_links": memory_validate_links,
        "memory_reorganize_preview": memory_reorganize_preview,
        "memory_suggest_structure": memory_suggest_structure,
        "memory_suggest_links": memory_suggest_links,
        "memory_score_existing_links": memory_score_existing_links,
        "memory_score_links_by_access": memory_score_links_by_access,
        "memory_check_cross_references": memory_check_cross_references,
        "memory_cross_domain_links": memory_cross_domain_links,
        "memory_surface_unlinked": memory_surface_unlinked,
        "memory_link_delta": memory_link_delta,
    }
