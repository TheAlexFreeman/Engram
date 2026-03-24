"""Pure-Python knowledge-graph analysis and pruning engine.

Provides graph construction from the knowledge base, structural metrics
(clustering, betweenness, small-world σ, per-domain density), duplicate
link detection, and redundant link pruning.
"""

from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..frontmatter_utils import read_with_frontmatter, write_with_frontmatter
from .reference_extractor import (
    _MARKDOWN_LINK_RE,
    _iter_governed_markdown_files_in_scope,
    _resolve_reference,
)

_KNOWLEDGE_PREFIX = "memory/knowledge/"


def _knowledge_domain(rel_path: str) -> str:
    """Extract domain name from a knowledge-relative path."""
    if not rel_path.startswith(_KNOWLEDGE_PREFIX):
        return ""
    remainder = rel_path[len(_KNOWLEDGE_PREFIX) :]
    return remainder.split("/", 1)[0] if "/" in remainder else ""


# ── Graph construction ─────────────────────────────────────────────


def build_knowledge_graph(root: Path, scope: str = "") -> dict[str, Any]:
    """Walk knowledge files and return ``{nodes, edges}`` adjacency data.

    *root* is the content root (``core/``).  *scope* can narrow to a
    sub-folder such as ``"knowledge/mathematics"``.
    """
    scope = scope or "knowledge"

    file_list = _iter_governed_markdown_files_in_scope(root, scope)
    # Restrict to knowledge tree
    file_list = [p for p in file_list if p.startswith(_KNOWLEDGE_PREFIX)]

    node_set: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()

    for rel_path in file_list:
        if rel_path.endswith("/SUMMARY.md"):
            continue
        domain = _knowledge_domain(rel_path)
        node_set.setdefault(rel_path, {"id": rel_path, "domain": domain})

        abs_path = root / rel_path
        try:
            frontmatter, body = read_with_frontmatter(abs_path)
        except OSError:
            continue

        # Frontmatter `related:` list
        related = frontmatter.get("related", [])
        if isinstance(related, str):
            related = [r.strip() for r in related.split(",") if r.strip()]
        if isinstance(related, list):
            for raw in related:
                if not isinstance(raw, str):
                    continue
                resolved = _resolve_reference(rel_path, raw, root)
                if resolved and resolved.startswith(_KNOWLEDGE_PREFIX):
                    _add_edge(rel_path, resolved, edges, seen_edges, node_set)

        # Markdown body links
        for m in _MARKDOWN_LINK_RE.finditer(body):
            raw_target = m.group(2)
            resolved = _resolve_reference(rel_path, raw_target, root)
            if resolved and resolved.startswith(_KNOWLEDGE_PREFIX):
                _add_edge(rel_path, resolved, edges, seen_edges, node_set)

    nodes = list(node_set.values())
    return {"nodes": nodes, "edges": edges}


def _add_edge(
    source: str,
    target: str,
    edges: list[dict[str, str]],
    seen: set[tuple[str, str]],
    node_set: dict[str, dict[str, Any]],
) -> None:
    if source == target:
        return
    key = (min(source, target), max(source, target))
    if key in seen:
        return
    seen.add(key)
    edges.append({"source": source, "target": target})
    if target not in node_set:
        node_set[target] = {"id": target, "domain": _knowledge_domain(target)}


# ── Graph metrics ──────────────────────────────────────────────────


def analyze_graph(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> dict[str, Any]:
    """Compute structural metrics on a knowledge graph.

    Port of the browser-side ``analyzeGraph()`` in graph.js.
    Returns clustering coefficient, betweenness centrality,
    small-world σ, per-domain stats, bridges, hubs, and orphans.
    """
    N = len(nodes)
    E = len(edges)
    if N < 2:
        return {"insufficient": True, "nodes": N, "edges": E}

    idx_by_id: dict[str, int] = {n["id"]: i for i, n in enumerate(nodes)}
    adj: list[list[int]] = [[] for _ in range(N)]
    for e in edges:
        si, ti = idx_by_id.get(e["source"]), idx_by_id.get(e["target"])
        if si is not None and ti is not None:
            adj[si].append(ti)
            adj[ti].append(si)

    degree = [len(adj[i]) for i in range(N)]

    # Clustering coefficient per node
    cluster_coeff = [0.0] * N
    for i in range(N):
        nb = adj[i]
        k = len(nb)
        if k < 2:
            continue
        nb_set = set(nb)
        triangles = 0
        for a in nb:
            for b in adj[a]:
                if b in nb_set and b > a:
                    triangles += 1
        cluster_coeff[i] = (2 * triangles) / (k * (k - 1))

    avg_clustering = sum(cluster_coeff) / N

    # Sampled BFS for average path length + Brandes betweenness
    sample_size = min(N, 100)
    sample_idx = list(range(N)) if sample_size == N else random.sample(range(N), sample_size)

    total_dist = 0
    pair_count = 0
    betweenness = [0.0] * N

    for src in sample_idx:
        dist, sigma, order = _bfs(adj, N, src)
        for v in range(N):
            if dist[v] > 0:
                total_dist += dist[v]
                pair_count += 1
        # Brandes accumulation
        delta = [0.0] * N
        for w in reversed(order):
            for v in adj[w]:
                if dist[v] == dist[w] - 1 and sigma[v] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != src:
                betweenness[w] += delta[w]

    # Scale by sampling ratio
    scale = N / sample_size
    betweenness = [b * scale for b in betweenness]

    avg_path_length = total_dist / pair_count if pair_count else 0.0

    # Erdős–Rényi random baselines
    avg_degree = (2 * E) / N if N else 0.0
    c_random = avg_degree / (N - 1) if N > 1 else 0.0
    l_random = math.log(N) / math.log(avg_degree) if avg_degree > 1 and N > 1 else 0.0

    # Small-world σ (Humphries-Gurney)
    sigma = 0.0
    if c_random > 0 and l_random > 0 and avg_path_length > 0:
        c_ratio = avg_clustering / c_random
        l_ratio = avg_path_length / l_random
        sigma = c_ratio / l_ratio if l_ratio > 0 else 0.0

    # Per-domain analysis
    global_density = (2 * E) / (N * (N - 1)) if N > 1 else 0.0
    domain_nodes: dict[str, list[int]] = defaultdict(list)
    for i, n in enumerate(nodes):
        domain_nodes[n.get("domain", "")].append(i)

    domains: list[dict[str, Any]] = []
    for d, d_indices in domain_nodes.items():
        dn = len(d_indices)
        dn_set = set(d_indices)
        internal = cross = 0
        for e in edges:
            si, ti = idx_by_id.get(e["source"]), idx_by_id.get(e["target"])
            if si is None or ti is None:
                continue
            s_in, t_in = si in dn_set, ti in dn_set
            if s_in and t_in:
                internal += 1
            elif s_in or t_in:
                cross += 1
        possible = (dn * (dn - 1)) // 2 if dn > 1 else 0
        density = internal / possible if possible else 0.0
        dom_clustering = sum(cluster_coeff[i] for i in d_indices) / dn if dn else 0.0

        status = "healthy"
        if global_density > 0:
            if density < global_density * 0.5:
                status = "sparse"
            elif density > global_density * 2:
                status = "dense"

        domains.append(
            {
                "name": d,
                "nodes": dn,
                "internal_edges": internal,
                "cross_edges": cross,
                "density": round(density, 4),
                "clustering": round(dom_clustering, 4),
                "status": status,
            }
        )
    domains.sort(key=lambda x: x["nodes"], reverse=True)

    # Bridges: betweenness > 2× median
    sorted_bw = sorted(betweenness)
    median_bw = sorted_bw[N // 2]
    bridge_threshold = max(median_bw * 2, 1.0)
    bridges = [
        {
            "id": nodes[i]["id"],
            "domain": nodes[i]["domain"],
            "betweenness": round(betweenness[i], 2),
        }
        for i in range(N)
        if betweenness[i] > bridge_threshold
    ]
    bridges.sort(key=lambda x: x["betweenness"], reverse=True)
    bridges = bridges[:15]

    # Hubs: top 5 by degree
    by_degree = sorted(range(N), key=lambda i: degree[i], reverse=True)
    hubs = [
        {"id": nodes[i]["id"], "domain": nodes[i]["domain"], "degree": degree[i]}
        for i in by_degree[:5]
    ]

    # Orphans: degree ≤ 1
    orphans = [
        {"id": nodes[i]["id"], "domain": nodes[i]["domain"], "degree": degree[i]}
        for i in range(N)
        if degree[i] <= 1
    ]

    return {
        "insufficient": False,
        "nodes": N,
        "edges": E,
        "avg_degree": round(avg_degree, 2),
        "avg_clustering": round(avg_clustering, 4),
        "avg_path_length": round(avg_path_length, 2),
        "sigma": round(sigma, 2),
        "global_density": round(global_density, 4),
        "domains": domains,
        "bridges": bridges,
        "hubs": hubs,
        "orphans": orphans,
    }


def _bfs(adj: list[list[int]], N: int, src: int) -> tuple[list[int], list[int], list[int]]:
    dist = [-1] * N
    sigma = [0] * N
    dist[src] = 0
    sigma[src] = 1
    queue = [src]
    head = 0
    order: list[int] = []
    while head < len(queue):
        u = queue[head]
        head += 1
        order.append(u)
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
            if dist[v] == dist[u] + 1:
                sigma[v] += sigma[u]
    return dist, sigma, order


# ── Duplicate / redundant link detection & pruning ─────────────────


def find_duplicate_links(root: Path, scope: str = "") -> list[dict[str, Any]]:
    """Scan knowledge files for duplicate link targets.

    Returns a list of per-file reports with duplicate targets and their
    locations (body vs Connections section).
    """
    scope = scope or "knowledge"
    file_list = _iter_governed_markdown_files_in_scope(root, scope)
    file_list = [p for p in file_list if p.startswith(_KNOWLEDGE_PREFIX)]

    results: list[dict[str, Any]] = []
    for rel_path in file_list:
        if rel_path.endswith("/SUMMARY.md"):
            continue
        abs_path = root / rel_path
        try:
            _fm, body = read_with_frontmatter(abs_path)
        except OSError:
            continue

        main_body, conn_section = _split_connections(body)
        body_targets = _collect_link_targets(main_body)
        conn_targets = _collect_link_targets(conn_section)

        dupes: list[dict[str, str]] = []
        # Connections entries duplicating body links
        for t in conn_targets:
            if t in body_targets:
                dupes.append({"target": t, "kind": "connections_duplicates_body"})
        # Duplicates within body
        seen: set[str] = set()
        for t in body_targets:
            if t in seen:
                dupes.append({"target": t, "kind": "duplicate_body_link"})
            seen.add(t)
        # Duplicates within Connections
        seen_conn: set[str] = set()
        for t in conn_targets:
            if t in seen_conn:
                dupes.append({"target": t, "kind": "duplicate_connections_link"})
            seen_conn.add(t)

        if dupes:
            results.append({"path": rel_path, "duplicates": dupes})

    return results


def prune_redundant_links(root: Path, scope: str = "", *, dry_run: bool = True) -> dict[str, Any]:
    """Remove redundant cross-references from knowledge files.

    Ported from the standalone ``prune_links.py`` script.

    When *dry_run* is True (default), no files are written — only a
    report is returned.  Returns ``{files_modified, total_removed,
    details}`` where *details* is a per-file breakdown.
    """
    scope = scope or "knowledge"
    file_list = _iter_governed_markdown_files_in_scope(root, scope)
    file_list = [p for p in file_list if p.startswith(_KNOWLEDGE_PREFIX)]

    total_removed = 0
    files_modified: list[str] = []
    details: list[dict[str, Any]] = []

    for rel_path in file_list:
        if rel_path.endswith("/SUMMARY.md"):
            continue
        abs_path = root / rel_path
        try:
            frontmatter, body = read_with_frontmatter(abs_path)
        except OSError:
            continue

        main_body, conn_section = _split_connections(body)
        body_targets = set(_collect_link_targets(main_body))
        removed_count = 0

        # 1. Remove Connections entries duplicating body links
        if conn_section and body_targets:
            new_conn_lines = []
            for line in conn_section.split("\n"):
                m = _MARKDOWN_LINK_RE.search(line)
                if m and m.group(2) in body_targets:
                    removed_count += 1
                    continue
                new_conn_lines.append(line)
            conn_section = "\n".join(new_conn_lines)

        # 2. Deduplicate body links (keep first occurrence)
        seen_in_body: set[str] = set()
        parts: list[str] = []
        pos = 0
        for m in _MARKDOWN_LINK_RE.finditer(main_body):
            target = m.group(2)
            if target in seen_in_body:
                parts.append(main_body[pos : m.start()])
                parts.append(m.group(1))  # plain text only
                pos = m.end()
                removed_count += 1
            else:
                seen_in_body.add(target)
                parts.append(main_body[pos : m.end()])
                pos = m.end()
        parts.append(main_body[pos:])
        main_body = "".join(parts)

        # 3. Deduplicate within Connections
        if conn_section:
            seen_conn: set[str] = set()
            new_conn_lines = []
            for line in conn_section.split("\n"):
                m = _MARKDOWN_LINK_RE.search(line)
                if m:
                    t = m.group(2)
                    if t in seen_conn:
                        removed_count += 1
                        continue
                    seen_conn.add(t)
                new_conn_lines.append(line)
            conn_section = "\n".join(new_conn_lines)

        # 4. Remove empty Connections section
        if conn_section and not _MARKDOWN_LINK_RE.search(conn_section):
            conn_section = ""

        if removed_count == 0:
            continue

        new_body = main_body + conn_section
        # Collapse triple+ blank lines
        new_body = re.sub(r"\n{3,}", "\n\n", new_body)

        if not dry_run:
            write_with_frontmatter(abs_path, frontmatter, new_body)

        total_removed += removed_count
        files_modified.append(rel_path)
        details.append({"path": rel_path, "removed": removed_count})

    return {
        "files_modified": files_modified,
        "total_removed": total_removed,
        "details": details,
        "dry_run": dry_run,
    }


# ── Helpers ────────────────────────────────────────────────────────


_CONNECTIONS_RE = re.compile(r"^(?:---\n\n)?## Connections\n", re.MULTILINE)


def _split_connections(body: str) -> tuple[str, str]:
    """Split body into (main_body, connections_section)."""
    m = _CONNECTIONS_RE.search(body)
    if m:
        return body[: m.start()], body[m.start() :]
    return body, ""


def _collect_link_targets(text: str) -> list[str]:
    """Return all markdown link targets in *text*, preserving order."""
    return [m.group(2) for m in _MARKDOWN_LINK_RE.finditer(text)]
