"""Graph analysis and pruning MCP tools (Tier 1 semantic)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from ...models import MemoryWriteResult

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


def register_tools(mcp: "FastMCP", get_repo, get_root) -> dict[str, object]:
    """Register graph-oriented knowledge tools."""

    tools: dict[str, object] = {}

    @mcp.tool(
        name="memory_analyze_graph",
        annotations=_tool_annotations(
            title="Analyze Knowledge Graph",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_analyze_graph(
        path: str = "",
        include_details: bool = False,
    ) -> str:
        """Compute structural metrics on the knowledge graph.

        Returns node/edge counts, clustering coefficient, betweenness
        centrality, small-world σ, per-domain density, bridges, hubs,
        and orphans.

          Call ``memory_tool_schema`` with ``"memory_analyze_graph"`` to
          inspect the scope and detail-toggle contract from an MCP client.

        Args:
            path: Optional scope — a domain folder like ``"knowledge/mathematics"``
                  or empty string for the full knowledge base.
            include_details: When True, additionally return the list of
                  duplicate links found across the scoped files.
        """
        from ..graph_analysis import (
            analyze_graph,
            build_knowledge_graph,
            find_duplicate_links,
        )

        root = get_root()
        graph = build_knowledge_graph(root, scope=path)
        metrics = analyze_graph(graph["nodes"], graph["edges"])

        result: dict[str, Any] = {
            "scope": path or "knowledge",
            "metrics": metrics,
        }
        if include_details:
            result["duplicate_links"] = find_duplicate_links(root, scope=path)

        return json.dumps(result, indent=2)

    tools["memory_analyze_graph"] = memory_analyze_graph

    @mcp.tool(
        name="memory_prune_redundant_links",
        annotations=_tool_annotations(
            title="Prune Redundant Knowledge Links",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prune_redundant_links(
        path: str = "",
        dry_run: bool = True,
    ) -> str:
        """Remove redundant cross-references from knowledge files.

        Removes: Connections entries that duplicate body links, duplicate
        body links (keeping first occurrence), duplicate Connections
        entries, and empty Connections sections.

          Call ``memory_tool_schema`` with ``"memory_prune_redundant_links"``
          to inspect the supported scope and dry-run contract from an MCP
          client.

        Args:
            path: Optional scope — a domain folder like ``"knowledge/mathematics"``
                  or empty string for the full knowledge base.
            dry_run: When True (default), report what *would* change without
                  writing anything.  Set to False to apply changes and commit.
        """
        from ..graph_analysis import prune_redundant_links

        root = get_root()
        report = prune_redundant_links(root, scope=path, dry_run=dry_run)

        if dry_run or not report["files_modified"]:
            return json.dumps(report, indent=2)

        # Tier 1: stage changed files and auto-commit
        repo = get_repo()
        for rel_path in report["files_modified"]:
            repo.add(rel_path)

        n = len(report["files_modified"])
        scope_label = path or "knowledge"
        commit_msg = (
            f"[curation] Prune {report['total_removed']} redundant links "
            f"from {n} files in {scope_label}"
        )
        commit_result = repo.commit(commit_msg)
        result = MemoryWriteResult.from_commit(
            files_changed=report["files_modified"],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "total_removed": report["total_removed"],
                "files_modified_count": n,
                "scope": scope_label,
                "details": report["details"],
                "dry_run": False,
            },
        )
        return result.to_json()

    tools["memory_prune_redundant_links"] = memory_prune_redundant_links

    @mcp.tool(
        name="memory_audit_link_density",
        annotations=_tool_annotations(
            title="Audit Link Density",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_audit_link_density(
        path: str = "",
        degree_threshold: int = 6,
        clustering_threshold: float = 0.5,
    ) -> str:
        """Identify navigably-redundant edges in highly-connected knowledge nodes.

        An edge is "redundant" if it is not a bridge in the graph — its
        removal would not disconnect any pair of nodes.  This tool flags such
        edges for nodes that already have high degree AND high local clustering
        coefficient, where most paths have multiple alternatives.

        Useful for finding over-connected cliques (e.g. rationalist-community)
        where some cross-references may be purely mechanical rather than
        genuinely useful for navigation.

        Call ``memory_tool_schema`` with ``"memory_audit_link_density"`` to
        inspect the path and threshold contract. Values below 1 for
        ``degree_threshold`` are clamped before the audit runs.

        Args:
            path: Optional scope — a domain folder like
                  ``"knowledge/rationalist-community"`` or empty for the full
                  knowledge base.
            degree_threshold: Minimum undirected degree for a node to be
                  examined (default 6).
            clustering_threshold: Minimum local clustering coefficient for a
                  node to be examined (default 0.5, i.e. 50% of neighbor pairs
                  are also connected to each other).
        """
        from ..graph_analysis import find_dense_redundant_links

        root = get_root()
        result = find_dense_redundant_links(
            root,
            scope=path,
            degree_threshold=max(1, int(degree_threshold)),
            clustering_threshold=float(clustering_threshold),
        )
        return json.dumps(result, indent=2)

    tools["memory_audit_link_density"] = memory_audit_link_density

    @mcp.tool(
        name="memory_prune_weak_links",
        annotations=_tool_annotations(
            title="Prune Weak Links",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_prune_weak_links(
        path: str = "",
        scope: str = "",
        min_structural_score: float = 1.0,
        min_access_score: int = 0,
        signal: str = "structural",
        dry_run: bool = True,
    ) -> str:
        """Remove low-quality cross-references from knowledge files.

        Composites structural scoring (stem overlap, directory proximity,
        co-citation, body mentions) and/or access-log co-occurrence to
        identify weak links.  Always runs as ``dry_run=True`` by default;
        set ``dry_run=False`` to apply changes and commit.

        Call ``memory_tool_schema`` with ``"memory_prune_weak_links"`` to
        inspect the path-versus-scope precedence, signal enum, and dry-run
        contract from an MCP client.

        Args:
            path: Restrict to a single file.  Overrides *scope*.
            scope: Restrict to a domain folder (e.g.
                   ``"knowledge/rationalist-community"``).  Ignored when *path*
                   is set.  Defaults to all knowledge files when both are empty.
            min_structural_score: Structural threshold — links scoring below
                   this are pruning candidates (default 1.0).
            min_access_score: Access threshold — links with fewer co-accesses
                   are candidates.  Only used when *signal* includes access
                   scoring (default 0 — flags everything with zero co-accesses).
            signal: ``"structural"`` (default) — use structural score only;
                    ``"access"`` — use access-log score only;
                    ``"combined"`` — BOTH signals must mark a link weak before
                    it is removed.
            dry_run: When True (default), return candidate report without
                   writing.  Set to False to apply removals and auto-commit.
        """
        from ..errors import ValidationError
        from ..graph_analysis import prune_weak_links

        valid_signals = frozenset({"structural", "access", "combined"})
        if signal not in valid_signals:
            raise ValidationError(f"signal must be one of: {', '.join(sorted(valid_signals))}")

        root = get_root()
        try:
            report = prune_weak_links(
                root,
                scope=scope,
                path=path,
                min_structural_score=float(min_structural_score),
                min_access_score=int(min_access_score),
                signal=signal,
                dry_run=dry_run,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if dry_run or not report["files_changed"]:
            return json.dumps(report, indent=2)

        # Commit the changes
        repo = get_repo()
        for rel_path in report["files_changed"]:
            repo.add(rel_path)

        n = len(report["files_changed"])
        scope_label = path or scope or "knowledge"
        commit_msg = (
            f"[curation] Prune {report['total_removed']} weak links "
            f"from {n} files in {scope_label} (signal={signal})"
        )
        commit_result = repo.commit(commit_msg)
        result = MemoryWriteResult.from_commit(
            files_changed=report["files_changed"],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "total_removed": report["total_removed"],
                "files_changed_count": n,
                "scope": scope_label,
                "signal": signal,
                "details": report["details"],
                "dry_run": False,
            },
        )
        return result.to_json()

    tools["memory_prune_weak_links"] = memory_prune_weak_links

    return tools
