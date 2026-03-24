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

    return tools
