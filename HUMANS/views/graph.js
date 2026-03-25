/**
 * EngramGraph — standalone knowledge-graph visualisation module.
 *
 * Usage (from the host page):
 *   EngramGraph.init({ el, showError, readFile, listDir,
 *     parseFrontmatter, parseFlatYaml, renderMarkdown,
 *     getRootHandle, getKnowledgeBase, getDetailPath,
 *     setDetailPath, showDetailView, viewFile });
 *   EngramGraph.open();          // opens with auto-detected scope
 *   EngramGraph.open('ai');      // opens scoped to a domain
 *   EngramGraph.stop();          // tears down the running sim
 */
(function (root) {
  'use strict';

  /* ── Dependencies (set via init) ─────────────────────── */
  var deps = null;

  /* ── Domain colours ──────────────────────────────────── */
  var DOMAIN_COLORS = {
    'ai':                    '#6ec6ff',
    'cognitive-science':     '#b39ddb',
    'literature':            '#ffab91',
    'mathematics':           '#80cbc4',
    'philosophy':            '#fff59d',
    'rationalist-community': '#ef9a9a',
    'self':                  '#a5d6a7',
    'social-science':        '#ce93d8',
    'software-engineering':  '#90caf9',
    '_unverified':           '#757575'
  };
  var DOMAIN_DEFAULT_COLOR = '#888888';

  function clearNode(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function formatNumber(value, digits) {
    return digits === undefined ? value.toString() : value.toFixed(digits);
  }

  function summarizeGraph(result, scope) {
    if (!result || result.insufficient) {
      return {
        title: 'Graph summary unavailable',
        sentences: ['The graph does not contain enough nodes to summarize.'],
        topDomains: [],
        topHubs: []
      };
    }

    var topDomains = result.domains.slice(0, 3).map(function (domain) {
      return {
        name: domain.name,
        nodes: domain.nodes,
        status: domain.status
      };
    });
    var topHubs = result.hubs.slice(0, 3).map(function (hub) {
      return {
        label: hub.label,
        domain: hub.domain,
        degree: hub.degree
      };
    });

    var scopeLabel = scope || 'all knowledge domains';
    var sentences = [
      'Scope: ' + scopeLabel + '.',
      'The graph contains ' + result.nodes + ' files and ' + result.edges + ' links, with an average degree of ' + formatNumber(result.avgDegree, 1) + '.',
      'Average path length is ' + formatNumber(result.avgPathLength, 2) + ' and average clustering is ' + formatNumber(result.avgClustering, 3) + '.',
      result.sigma > 1
        ? 'Small-world structure is present with sigma ' + formatNumber(result.sigma, 2) + '.'
        : (result.sigma > 0
            ? 'Small-world structure is weak with sigma ' + formatNumber(result.sigma, 2) + '.'
            : 'Small-world structure could not be computed from the current graph.'),
      result.bridges.length > 0
        ? 'Bridge nodes detected: ' + result.bridges.slice(0, 3).map(function (bridge) { return bridge.label; }).join(', ') + '.'
        : 'No strong bridge nodes were detected.',
      result.orphans.length > 0
        ? result.orphans.length + ' node' + (result.orphans.length === 1 ? '' : 's') + ' are isolated or weakly connected.'
        : 'No isolated or weakly connected nodes were detected.'
    ];

    return {
      title: 'Graph summary for ' + scopeLabel,
      sentences: sentences,
      topDomains: topDomains,
      topHubs: topHubs
    };
  }

  function appendTableHead(table, headers) {
    var thead = document.createElement('thead');
    var row = document.createElement('tr');
    for (var i = 0; i < headers.length; i++) {
      var th = document.createElement('th');
      th.textContent = headers[i];
      row.appendChild(th);
    }
    thead.appendChild(row);
    table.appendChild(thead);
  }

  function makeBadgeCell(text, className) {
    var td = document.createElement('td');
    var badge = document.createElement('span');
    badge.className = className;
    badge.textContent = text;
    td.appendChild(badge);
    return td;
  }

  /* ── Network analysis engine ─────────────────────────── */

  function analyzeGraph(nodes, edges) {
    var N = nodes.length;
    var E = edges.length;
    if (N < 2) return { insufficient: true, nodes: N, edges: E };

    var idxById = {};
    for (var i = 0; i < N; i++) idxById[nodes[i].id] = i;
    var adjList = new Array(N);
    for (var i = 0; i < N; i++) adjList[i] = [];
    for (var e = 0; e < E; e++) {
      var si = idxById[edges[e].source], ti = idxById[edges[e].target];
      if (si !== undefined && ti !== undefined) {
        adjList[si].push(ti);
        adjList[ti].push(si);
      }
    }

    function bfsFrom(src) {
      var dist = new Array(N);
      var sigma = new Array(N);
      for (var i = 0; i < N; i++) { dist[i] = -1; sigma[i] = 0; }
      dist[src] = 0; sigma[src] = 1;
      var queue = [src], head = 0;
      var order = [];
      while (head < queue.length) {
        var u = queue[head++];
        order.push(u);
        var nb = adjList[u];
        for (var j = 0; j < nb.length; j++) {
          var v = nb[j];
          if (dist[v] === -1) {
            dist[v] = dist[u] + 1;
            queue.push(v);
          }
          if (dist[v] === dist[u] + 1) sigma[v] += sigma[u];
        }
      }
      return { dist: dist, sigma: sigma, order: order, reachable: queue.length };
    }

    // Clustering coefficient per node
    var clusterCoeff = new Array(N);
    for (var i = 0; i < N; i++) {
      var nb = adjList[i];
      var k = nb.length;
      if (k < 2) { clusterCoeff[i] = 0; continue; }
      var triangles = 0;
      var nbSet = {};
      for (var a = 0; a < k; a++) nbSet[nb[a]] = true;
      for (var a = 0; a < k; a++) {
        var nba = adjList[nb[a]];
        for (var b = 0; b < nba.length; b++) {
          if (nbSet[nba[b]] && nba[b] > nb[a]) triangles++;
        }
      }
      clusterCoeff[i] = (2 * triangles) / (k * (k - 1));
    }
    var avgClustering = 0;
    for (var i = 0; i < N; i++) avgClustering += clusterCoeff[i];
    avgClustering /= N;

    // Sampled BFS for average path length + approximate betweenness
    var sampleSize = Math.min(N, 100);
    var sampleIdx = [];
    if (sampleSize === N) {
      for (var i = 0; i < N; i++) sampleIdx.push(i);
    } else {
      var pool = [];
      for (var i = 0; i < N; i++) pool.push(i);
      for (var i = 0; i < sampleSize; i++) {
        var pick = i + Math.floor(Math.random() * (N - i));
        var tmp = pool[i]; pool[i] = pool[pick]; pool[pick] = tmp;
        sampleIdx.push(pool[i]);
      }
    }

    var totalDist = 0, pairCount = 0;
    var betweenness = new Array(N);
    for (var i = 0; i < N; i++) betweenness[i] = 0;

    for (var s = 0; s < sampleIdx.length; s++) {
      var bfs = bfsFrom(sampleIdx[s]);
      for (var v = 0; v < N; v++) {
        if (bfs.dist[v] > 0) { totalDist += bfs.dist[v]; pairCount++; }
      }
      // Brandes-style betweenness accumulation
      var delta = new Array(N);
      for (var i = 0; i < N; i++) delta[i] = 0;
      for (var j = bfs.order.length - 1; j >= 0; j--) {
        var w = bfs.order[j];
        var nb = adjList[w];
        for (var k = 0; k < nb.length; k++) {
          var v = nb[k];
          if (bfs.dist[v] === bfs.dist[w] - 1 && bfs.sigma[v] > 0) {
            delta[v] += (bfs.sigma[v] / bfs.sigma[w]) * (1 + delta[w]);
          }
        }
        if (w !== sampleIdx[s]) betweenness[w] += delta[w];
      }
    }

    // Scale betweenness by sampling ratio
    var scale = N / sampleSize;
    for (var i = 0; i < N; i++) betweenness[i] *= scale;

    var avgPathLength = pairCount > 0 ? totalDist / pairCount : 0;

    // Random graph baselines (Erdos-Renyi)
    var avgDegree = N > 0 ? (2 * E) / N : 0;
    var cRandom = N > 1 ? avgDegree / (N - 1) : 0;
    var lRandom = (avgDegree > 1 && N > 1) ? Math.log(N) / Math.log(avgDegree) : 0;

    // Small-world coefficient sigma (Humphries-Gurney)
    var sigma = 0;
    if (cRandom > 0 && lRandom > 0 && avgPathLength > 0) {
      var cRatio = avgClustering / cRandom;
      var lRatio = avgPathLength / lRandom;
      sigma = lRatio > 0 ? cRatio / lRatio : 0;
    }

    // Per-domain analysis
    var domainNodes = {};
    for (var i = 0; i < N; i++) {
      var d = nodes[i].domain;
      if (!domainNodes[d]) domainNodes[d] = [];
      domainNodes[d].push(i);
    }

    var globalDensity = N > 1 ? (2 * E) / (N * (N - 1)) : 0;
    var domains = [];
    for (var d in domainNodes) {
      var dnodes = domainNodes[d];
      var dn = dnodes.length;
      var dnSet = {};
      for (var i = 0; i < dn; i++) dnSet[dnodes[i]] = true;
      var internalEdges = 0, crossEdges = 0;
      for (var e = 0; e < E; e++) {
        var si = idxById[edges[e].source], ti = idxById[edges[e].target];
        var sIn = !!dnSet[si], tIn = !!dnSet[ti];
        if (sIn && tIn) internalEdges++;
        else if (sIn || tIn) crossEdges++;
      }
      var possibleInternal = dn > 1 ? (dn * (dn - 1)) / 2 : 0;
      var density = possibleInternal > 0 ? internalEdges / possibleInternal : 0;
      var domClustering = 0;
      for (var i = 0; i < dn; i++) domClustering += clusterCoeff[dnodes[i]];
      domClustering = dn > 0 ? domClustering / dn : 0;

      var status = 'healthy';
      if (globalDensity > 0) {
        if (density < globalDensity * 0.5) status = 'sparse';
        else if (density > globalDensity * 2) status = 'dense';
      }

      domains.push({
        name: d, nodes: dn, internalEdges: internalEdges,
        crossEdges: crossEdges, density: density,
        clustering: domClustering, status: status,
        nodeIndices: dnodes
      });
    }
    domains.sort(function (a, b) { return b.nodes - a.nodes; });

    // Bridge/bottleneck detection
    var sortedBw = betweenness.slice().sort(function (a, b) { return a - b; });
    var medianBw = sortedBw[Math.floor(N / 2)];
    var bridgeThreshold = Math.max(medianBw * 2, 1);
    var bridges = [];
    for (var i = 0; i < N; i++) {
      if (betweenness[i] > bridgeThreshold) {
        bridges.push({ index: i, id: nodes[i].id, label: nodes[i].label,
          domain: nodes[i].domain, betweenness: betweenness[i] });
      }
    }
    bridges.sort(function (a, b) { return b.betweenness - a.betweenness; });
    bridges = bridges.slice(0, 15);

    // Hub identification: top 5 by degree
    var byDegree = [];
    for (var i = 0; i < N; i++) {
      byDegree.push({ index: i, id: nodes[i].id, label: nodes[i].label,
        domain: nodes[i].domain, degree: nodes[i].degree });
    }
    byDegree.sort(function (a, b) { return b.degree - a.degree; });
    var hubs = byDegree.slice(0, 5);

    // Orphan detection: degree 0 or 1
    var orphans = [];
    for (var i = 0; i < N; i++) {
      if (nodes[i].degree <= 1) {
        orphans.push({ index: i, id: nodes[i].id, label: nodes[i].label,
          domain: nodes[i].domain, degree: nodes[i].degree });
      }
    }

    return {
      insufficient: false,
      nodes: N, edges: E,
      avgDegree: avgDegree,
      avgClustering: avgClustering,
      avgPathLength: avgPathLength,
      cRandom: cRandom, lRandom: lRandom,
      sigma: sigma,
      globalDensity: globalDensity,
      domains: domains,
      bridges: bridges,
      hubs: hubs,
      orphans: orphans,
      clusterCoeff: clusterCoeff,
      betweenness: betweenness,
      bridgeThreshold: bridgeThreshold
    };
  }

  /* ── Reference extraction ────────────────────────────── */

  function resolveGraphRef(ref, sourceDir) {
    var path = ref.replace(/^knowledge\//, '').replace(/#.*$/, '');
    if (path.match(/^(self|_unverified)\//)) {
      // already relative to knowledge root
    } else if (path.match(/^\.\.\//) || path.match(/^\.\//)) {
      var base = sourceDir.slice();
      var parts = path.split('/');
      for (var k = 0; k < parts.length; k++) {
        if (parts[k] === '..') base.pop();
        else if (parts[k] !== '.') base.push(parts[k]);
      }
      path = base.join('/');
    }
    if (!path.match(/\.md$/i)) path += '.md';
    return path;
  }

  function extractRefs(content) {
    var refs = [];
    var parsed = deps.parseFrontmatter(content);

    // 1) related: frontmatter field
    if (parsed.frontmatter) {
      var fm = deps.parseFlatYaml(parsed.frontmatter);
      if (fm.related) {
        var items = fm.related.split(/,\s*/);
        for (var i = 0; i < items.length; i++) {
          var r = items[i].trim();
          if (r && r.match(/\.md(?:#.*)?$/i)) refs.push(r.replace(/#.*$/, ''));
        }
      }
      var listMatch = parsed.frontmatter.match(/^related:\s*\n((?:\s+-\s+.+\n?)+)/m);
      if (listMatch) {
        var listItems = listMatch[1].match(/^\s+-\s+(.+)/gm);
        if (listItems) {
          for (var j = 0; j < listItems.length; j++) {
            var val = listItems[j].replace(/^\s+-\s+/, '').trim();
            if (val) {
              var normalized = val.replace(/#.*$/, '');
              refs.push(normalized.match(/\.md$/i) ? normalized : normalized + '.md');
            }
          }
        }
      }
    }

    // 2) Markdown links to .md files in body
    var linkRx = /\[([^\]]*)\]\(([^)]+\.md(?:#[^)]+)?)\)/gi;
    var m;
    while ((m = linkRx.exec(parsed.body)) !== null) {
      if (!m[2].match(/^https?:\/\//i)) refs.push(m[2].replace(/#.*$/, ''));
    }

    // 3) Backtick-wrapped .md file references
    var btRx = /`([^`]+\.md(?:#[^`]+)?)`/gi;
    while ((m = btRx.exec(parsed.body)) !== null) {
      refs.push(m[1].replace(/#.*$/, ''));
    }

    return refs;
  }

  /* ── File collection & graph building ────────────────── */

  async function collectFiles(handle, prefix) {
    var results = [];
    var listing = await deps.listDir(handle, prefix);
    var knowledgeBase = deps.getKnowledgeBase();

    for (var f = 0; f < listing.files.length; f++) {
      if (listing.files[f].endsWith('.md')) {
        var segments = prefix.split('/').filter(Boolean);
        var kbParts = knowledgeBase.split('/');
        var relSegments = segments.slice(kbParts.length);
        results.push({
          path: (relSegments.length ? relSegments.join('/') + '/' : '') + listing.files[f],
          dirSegments: relSegments
        });
      }
    }

    for (var d = 0; d < listing.dirs.length; d++) {
      var dirName = listing.dirs[d];
      if (dirName === '__pycache__') continue;
      var sub = await collectFiles(handle, prefix + '/' + dirName);
      for (var s = 0; s < sub.length; s++) results.push(sub[s]);
    }
    return results;
  }

  async function buildGraph(progressCb, filterPrefix) {
    var knowledgeBase = deps.getKnowledgeBase();
    var rootHandle = deps.getRootHandle();
    var scanRoot = knowledgeBase;
    if (filterPrefix) scanRoot = knowledgeBase + '/' + filterPrefix;
    var files = await collectFiles(rootHandle, scanRoot);
    if (progressCb) progressCb('Found ' + files.length + ' files, scanning\u2026');

    if (filterPrefix) {
      for (var fi = 0; fi < files.length; fi++) {
        files[fi].path = filterPrefix + '/' + files[fi].path;
        var pathParts = files[fi].path.split('/');
        files[fi].dirSegments = pathParts.slice(0, pathParts.length - 1);
      }
    }

    var nodeMap = {};
    var edges = [];

    for (var i = 0; i < files.length; i++) {
      var fpath = files[i].path;
      var domain = files[i].dirSegments[0] || '_root';
      nodeMap[fpath] = {
        id: fpath,
        domain: domain,
        label: fpath.split('/').pop().replace(/\.md$/, ''),
        refs: 0, refBy: 0,
        external: false
      };
    }

    var batchSize = 20;
    var pendingExternal = [];
    for (var b = 0; b < files.length; b += batchSize) {
      var batch = files.slice(b, Math.min(b + batchSize, files.length));
      var reads = batch.map(function (f) {
        return deps.readFile(rootHandle, knowledgeBase + '/' + f.path);
      });
      var contents = await Promise.all(reads);
      for (var j = 0; j < batch.length; j++) {
        if (!contents[j]) continue;
        var rawRefs = extractRefs(contents[j]);
        var sourceId = batch[j].path;
        var seen = {};
        for (var r = 0; r < rawRefs.length; r++) {
          var targetId = resolveGraphRef(rawRefs[r], batch[j].dirSegments);
          if (targetId === sourceId || seen[targetId]) continue;
          seen[targetId] = true;
          if (nodeMap[targetId]) {
            edges.push({ source: sourceId, target: targetId });
            nodeMap[sourceId].refs++;
            nodeMap[targetId].refBy++;
          } else if (filterPrefix) {
            pendingExternal.push({ source: sourceId, target: targetId });
          }
        }
      }
      if (progressCb) progressCb('Scanned ' + Math.min(b + batchSize, files.length) + ' / ' + files.length);
    }

    if (filterPrefix && pendingExternal.length > 0) {
      for (var pe = 0; pe < pendingExternal.length; pe++) {
        var tid = pendingExternal[pe].target;
        if (!nodeMap[tid]) {
          var tParts = tid.split('/');
          var tDomain = tParts[0] || '_root';
          nodeMap[tid] = {
            id: tid,
            domain: tDomain,
            label: tParts[tParts.length - 1].replace(/\.md$/, ''),
            refs: 0, refBy: 0,
            external: true
          };
        }
        edges.push({ source: pendingExternal[pe].source, target: tid });
        nodeMap[pendingExternal[pe].source].refs++;
        nodeMap[tid].refBy++;
      }
    }

    var nodes = [];
    for (var id in nodeMap) nodes.push(nodeMap[id]);
    return { nodes: nodes, edges: edges, scope: filterPrefix || null };
  }

  /* ── Force-directed layout + canvas renderer ────────── */

  var graphSim = null;

  function startGraph(graph) {
    var el = deps.el;
    var overlay = document.getElementById('graph-overlay');
    var canvas = document.getElementById('graph-canvas');
    var ctx = canvas.getContext('2d');
    var tooltip = document.getElementById('graph-tooltip');
    var legend = document.getElementById('graph-legend');
    var stats = document.getElementById('graph-stats');
    var a11ySummary = document.getElementById('graph-accessible-summary');

    stats.textContent = graph.nodes.length + ' files \u00B7 ' + graph.edges.length + ' links';
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('tabindex', '0');
    canvas.setAttribute('aria-label', 'Interactive knowledge graph canvas');

    function renderAccessibleSummary(result) {
      if (!a11ySummary) return;
      clearNode(a11ySummary);
      var summary = summarizeGraph(result, graph.scope || 'all knowledge domains');
      a11ySummary.setAttribute('aria-label', summary.title);

      var title = document.createElement('h3');
      title.textContent = summary.title;
      a11ySummary.appendChild(title);

      for (var si = 0; si < summary.sentences.length; si++) {
        var p = document.createElement('p');
        p.textContent = summary.sentences[si];
        a11ySummary.appendChild(p);
      }

      if (summary.topDomains.length > 0) {
        var domainTitle = document.createElement('p');
        domainTitle.className = 'graph-summary-label';
        domainTitle.textContent = 'Largest domains';
        a11ySummary.appendChild(domainTitle);

        var domainList = document.createElement('ul');
        for (var di = 0; di < summary.topDomains.length; di++) {
          var domainItem = document.createElement('li');
          var domain = summary.topDomains[di];
          domainItem.textContent = domain.name + ': ' + domain.nodes + ' nodes (' + domain.status + ')';
          domainList.appendChild(domainItem);
        }
        a11ySummary.appendChild(domainList);
      }

      if (summary.topHubs.length > 0) {
        var hubTitle = document.createElement('p');
        hubTitle.className = 'graph-summary-label';
        hubTitle.textContent = 'Top hubs';
        a11ySummary.appendChild(hubTitle);

        var hubList = document.createElement('ul');
        for (var hi = 0; hi < summary.topHubs.length; hi++) {
          var hubItem = document.createElement('li');
          var hub = summary.topHubs[hi];
          hubItem.textContent = hub.label + ' (' + hub.domain + ', degree ' + hub.degree + ')';
          hubList.appendChild(hubItem);
        }
        a11ySummary.appendChild(hubList);
      }
    }

    function resize() {
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // Build legend (clickable domain filter)
    legend.textContent = '';
    var ltitle = el('div', 'Domains', 'legend-title');
    legend.appendChild(ltitle);
    var domainsSeen = {};
    for (var i = 0; i < graph.nodes.length; i++) {
      domainsSeen[graph.nodes[i].domain] = true;
    }
    var selectedDomain = null;
    var legendItems = {};
    for (var d in domainsSeen) {
      var item = el('div', '', 'legend-item');
      var dot = el('span', '', 'legend-dot');
      dot.style.background = DOMAIN_COLORS[d] || DOMAIN_DEFAULT_COLOR;
      item.appendChild(dot);
      item.appendChild(el('span', d));
      item.dataset.domain = d;
      legendItems[d] = item;
      (function (domain, itemEl) {
        itemEl.addEventListener('click', function () {
          if (selectedDomain === domain) {
            selectedDomain = null;
          } else {
            selectedDomain = domain;
          }
          for (var key in legendItems) {
            legendItems[key].classList.remove('active', 'dimmed');
            if (selectedDomain) {
              legendItems[key].classList.add(key === selectedDomain ? 'active' : 'dimmed');
            }
          }
        });
      })(d, item);
      legend.appendChild(item);
    }

    // Initialize node positions
    var W = canvas.width, H = canvas.height;
    var nodes = graph.nodes;
    var edges = graph.edges;

    var idxMap = {};
    for (var n = 0; n < nodes.length; n++) {
      idxMap[nodes[n].id] = n;
      nodes[n].x = W / 2 + (Math.random() - 0.5) * W * 0.6;
      nodes[n].y = H / 2 + (Math.random() - 0.5) * H * 0.6;
      nodes[n].vx = 0;
      nodes[n].vy = 0;
      nodes[n].degree = nodes[n].refs + nodes[n].refBy;
    }

    var edgeIdx = edges.map(function (e) {
      return { s: idxMap[e.source], t: idxMap[e.target] };
    });

    var adj = {};
    for (var e = 0; e < edges.length; e++) {
      var si = idxMap[edges[e].source], ti = idxMap[edges[e].target];
      if (!adj[si]) adj[si] = [];
      if (!adj[ti]) adj[ti] = [];
      adj[si].push(ti);
      adj[ti].push(si);
    }

    var cam = { x: W / 2, y: H / 2, zoom: 1 };
    var dragging = false, dragStart = null, camStart = null;
    var hoveredNode = -1;
    var dragNode = -1;

    var analysisResult = null;
    var analysisHighlight = { bridges: false, hubs: false, orphans: false, domain: null };
    var bridgeSet = {}, hubSet = {}, orphanSet = {};

    function fitToView() {
      if (nodes.length === 0) return;
      var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].x < minX) minX = nodes[i].x;
        if (nodes[i].x > maxX) maxX = nodes[i].x;
        if (nodes[i].y < minY) minY = nodes[i].y;
        if (nodes[i].y > maxY) maxY = nodes[i].y;
      }
      var pad = 40;
      var bw = (maxX - minX) + pad * 2;
      var bh = (maxY - minY) + pad * 2;
      cam.x = (minX + maxX) / 2;
      cam.y = (minY + maxY) / 2;
      cam.zoom = Math.min(canvas.width / bw, canvas.height / bh, 1);
      cam.zoom = Math.max(0.1, cam.zoom);
    }

    function screenToWorld(sx, sy) {
      return {
        x: (sx - canvas.width / 2) / cam.zoom + cam.x,
        y: (sy - canvas.height / 2) / cam.zoom + cam.y
      };
    }

    function nodeAt(wx, wy) {
      var pad = Math.max(6, 12 / cam.zoom);
      for (var i = nodes.length - 1; i >= 0; i--) {
        var r = nodeRadius(nodes[i]) / cam.zoom;
        var dx = nodes[i].x - wx, dy = nodes[i].y - wy;
        if (dx * dx + dy * dy < (r + pad) * (r + pad)) return i;
      }
      return -1;
    }

    function nodeRadius(node) {
      return Math.min(3 + node.degree * 1.2, 18);
    }

    // Interaction
    canvas.addEventListener('mousedown', function (ev) {
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      if (hit >= 0) {
        dragNode = hit;
        nodes[hit].pinned = true;
      } else {
        dragging = true;
        dragStart = { x: ev.clientX, y: ev.clientY };
        camStart = { x: cam.x, y: cam.y };
      }
    });

    canvas.addEventListener('mousemove', function (ev) {
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      if (dragNode >= 0) {
        var w = screenToWorld(sx, sy);
        nodes[dragNode].x = w.x;
        nodes[dragNode].y = w.y;
        nodes[dragNode].vx = 0;
        nodes[dragNode].vy = 0;
        return;
      }
      if (dragging) {
        cam.x = camStart.x - (ev.clientX - dragStart.x) / cam.zoom;
        cam.y = camStart.y - (ev.clientY - dragStart.y) / cam.zoom;
        return;
      }
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      hoveredNode = hit;
      canvas.style.cursor = hit >= 0 ? 'pointer' : 'grab';

      if (hit >= 0) {
        var node = nodes[hit];
        tooltip.style.display = '';
        tooltip.style.left = (ev.clientX - rect.left + 12) + 'px';
        tooltip.style.top = (ev.clientY - rect.top - 8) + 'px';
        tooltip.innerHTML = '';
        tooltip.appendChild(el('div', node.label));
        tooltip.appendChild(el('div', node.id, 'tt-path'));
        tooltip.appendChild(el('div', node.refs + ' out \u00B7 ' + node.refBy + ' in', 'tt-refs'));
      } else {
        tooltip.style.display = 'none';
      }
    });

    canvas.addEventListener('mouseup', function () {
      if (dragNode >= 0) {
        nodes[dragNode].pinned = false;
        dragNode = -1;
      }
      dragging = false;
    });

    // Preview panel
    var preview = document.getElementById('graph-preview');
    var previewTitle = document.getElementById('graph-preview-title');
    var previewMeta = document.getElementById('graph-preview-meta');
    var previewBody = document.getElementById('graph-preview-body');
    var previewOpen = document.getElementById('graph-preview-open');
    var previewClose = document.getElementById('graph-preview-close');
    var previewResize = document.getElementById('graph-preview-resize');
    var previewNodeId = null;

    function closePreview() {
      preview.classList.remove('visible');
      previewNodeId = null;
    }

    function closeOverlay() {
      closePreview();
      closeAnalysis();
      overlay.classList.remove('visible');
      if (graphSim) { graphSim.stop(); graphSim = null; }
    }

    // Resize handle
    (function () {
      var resizing = false, startX = 0, startW = 0;
      previewResize.addEventListener('mousedown', function (ev) {
        ev.preventDefault(); ev.stopPropagation();
        resizing = true; startX = ev.clientX;
        startW = preview.offsetWidth;
        previewResize.classList.add('active');
      });
      window.addEventListener('mousemove', function (ev) {
        if (!resizing) return;
        var newW = Math.max(220, Math.min(startW + (startX - ev.clientX), preview.parentElement.offsetWidth - 60));
        preview.style.width = newW + 'px';
      });
      window.addEventListener('mouseup', function () {
        if (resizing) { resizing = false; previewResize.classList.remove('active'); }
      });
    })();

    previewClose.addEventListener('click', closePreview);

    async function showPreviewNode(node) {
      previewNodeId = node.id;

      previewTitle.textContent = node.label;
      previewMeta.textContent = '';
      previewMeta.style.display = 'none';
      previewBody.textContent = 'Loading\u2026';
      preview.classList.add('visible');

      previewOpen.onclick = function () {
        var segs = node.id.split('/');
        var file = segs.pop();
        deps.setDetailPath(segs);
        closePreview();
        document.getElementById('graph-overlay').classList.remove('visible');
        if (graphSim) { graphSim.stop(); graphSim = null; }
        deps.showDetailView();
        deps.viewFile(file);
      };

      var knowledgeBase = deps.getKnowledgeBase();
      var rootHandle = deps.getRootHandle();
      var content = await deps.readFile(rootHandle, knowledgeBase + '/' + node.id);
      if (previewNodeId !== node.id) return;

      if (!content) {
        previewBody.textContent = 'Could not read file.';
        return;
      }

      var parsed = deps.parseFrontmatter(content);

      if (parsed.frontmatter) {
        var fm = deps.parseFlatYaml(parsed.frontmatter);
        previewMeta.textContent = '';
        previewMeta.style.display = '';
        var metaFields = ['trust', 'type', 'source', 'created'];
        for (var mf = 0; mf < metaFields.length; mf++) {
          if (!fm[metaFields[mf]]) continue;
          var tag = el('span', metaFields[mf] + ': ' + fm[metaFields[mf]], 'preview-tag');
          if (metaFields[mf] === 'trust') {
            var tv = fm.trust.toLowerCase();
            tag.className = 'preview-tag preview-trust-' + (tv === 'high' ? 'high' : tv === 'medium' ? 'med' : 'low');
          }
          previewMeta.appendChild(tag);
        }
        if (previewMeta.childNodes.length === 0) previewMeta.style.display = 'none';
      }

      previewBody.textContent = '';
      deps.renderMarkdown(parsed.body.trim(), previewBody);
    }

    canvas.addEventListener('dblclick', function (ev) {
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      if (hit < 0) { closePreview(); return; }
      showPreviewNode(nodes[hit]);
    });

    canvas.addEventListener('click', function (ev) {
      if (!preview.classList.contains('visible')) return;
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      if (hit < 0 || nodes[hit].id === previewNodeId) return;
      showPreviewNode(nodes[hit]);
    });

    canvas.addEventListener('wheel', function (ev) {
      ev.preventDefault();
      var rect = canvas.getBoundingClientRect();
      var sx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      var sy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      var wx = (sx - canvas.width / 2) / cam.zoom + cam.x;
      var wy = (sy - canvas.height / 2) / cam.zoom + cam.y;
      var factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
      var newZoom = Math.max(0.1, Math.min(8, cam.zoom * factor));
      cam.x = wx - (sx - canvas.width / 2) / newZoom;
      cam.y = wy - (sy - canvas.height / 2) / newZoom;
      cam.zoom = newZoom;
    }, { passive: false });

    // Physics step
    function step() {
      var alpha = 0.3;
      var repulsion = 800;
      var springLen = 80;
      var springK = 0.015;
      var centerK = 0.002;
      var damping = 0.88;

      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].pinned) continue;
        nodes[i].vx += (W / 2 - nodes[i].x) * centerK;
        nodes[i].vy += (H / 2 - nodes[i].y) * centerK;
      }

      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].pinned) continue;
        for (var j = i + 1; j < nodes.length; j++) {
          var dx = nodes[i].x - nodes[j].x;
          var dy = nodes[i].y - nodes[j].y;
          var dist2 = dx * dx + dy * dy;
          if (dist2 < 1) dist2 = 1;
          var force = repulsion / dist2;
          var fx = dx * force;
          var fy = dy * force;
          nodes[i].vx += fx;
          nodes[i].vy += fy;
          if (!nodes[j].pinned) {
            nodes[j].vx -= fx;
            nodes[j].vy -= fy;
          }
        }
      }

      for (var e = 0; e < edgeIdx.length; e++) {
        var a = nodes[edgeIdx[e].s], b = nodes[edgeIdx[e].t];
        var dx = b.x - a.x, dy = b.y - a.y;
        var dist = Math.sqrt(dx * dx + dy * dy) || 1;
        var disp = (dist - springLen) * springK;
        var fx = dx / dist * disp;
        var fy = dy / dist * disp;
        if (!a.pinned) { a.vx += fx; a.vy += fy; }
        if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
      }

      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].pinned) continue;
        nodes[i].vx *= damping;
        nodes[i].vy *= damping;
        nodes[i].x += nodes[i].vx * alpha;
        nodes[i].y += nodes[i].vy * alpha;
      }
    }

    // Render
    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.scale(cam.zoom, cam.zoom);
      ctx.translate(-cam.x, -cam.y);

      var highlightSet = {};
      var hoverActive = hoveredNode >= 0;
      if (hoverActive) {
        highlightSet[hoveredNode] = true;
        var neighbors = adj[hoveredNode] || [];
        for (var h = 0; h < neighbors.length; h++) highlightSet[neighbors[h]] = true;
      }
      var domainSet = {};
      var domainActive = selectedDomain !== null;
      if (domainActive) {
        for (var di = 0; di < nodes.length; di++) {
          if (nodes[di].domain === selectedDomain) domainSet[di] = true;
        }
      }
      var hasHighlight = hoverActive || domainActive;

      // Edges
      for (var e = 0; e < edgeIdx.length; e++) {
        var a = nodes[edgeIdx[e].s], b = nodes[edgeIdx[e].t];
        var edgeHover = hoverActive && highlightSet[edgeIdx[e].s] && highlightSet[edgeIdx[e].t];
        var edgeDomain = !hoverActive && domainActive && (domainSet[edgeIdx[e].s] || domainSet[edgeIdx[e].t]);
        var highlighted = edgeHover || edgeDomain;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = highlighted ? 'rgba(194,180,154,0.6)' : 'rgba(194,180,154,0.1)';
        ctx.lineWidth = highlighted ? 1.5 / cam.zoom : 0.5 / cam.zoom;
        ctx.stroke();
      }

      // Nodes
      for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var r = nodeRadius(node);
        var color = DOMAIN_COLORS[node.domain] || DOMAIN_DEFAULT_COLOR;
        var dimmedByHover = hoverActive && !highlightSet[i];
        var dimmedByDomain = !hoverActive && domainActive && !domainSet[i];
        var dimmed = dimmedByHover || dimmedByDomain;
        var isExternal = node.external;

        var drawR = r;
        if (analysisHighlight.hubs && hubSet[i]) drawR = r * 1.5;

        ctx.beginPath();
        ctx.arc(node.x, node.y, drawR / cam.zoom, 0, Math.PI * 2);
        if (isExternal) {
          ctx.fillStyle = 'rgba(60,55,50,0.3)';
          ctx.fill();
          ctx.setLineDash([3 / cam.zoom, 3 / cam.zoom]);
          ctx.strokeStyle = dimmed ? 'rgba(120,115,110,0.3)' : color;
          ctx.lineWidth = 1.5 / cam.zoom;
          ctx.stroke();
          ctx.setLineDash([]);
        } else {
          ctx.fillStyle = dimmed ? 'rgba(60,55,50,0.5)' : color;
          ctx.fill();
        }

        if (i === hoveredNode) {
          ctx.setLineDash([]);
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2 / cam.zoom;
          ctx.stroke();
        }

        // Analysis: bridge halo
        if (analysisHighlight.bridges && bridgeSet[i]) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, (drawR + 5) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#42a5f5';
          ctx.lineWidth = 2 / cam.zoom;
          ctx.setLineDash([]);
          ctx.stroke();
        }
        // Analysis: hub glow
        if (analysisHighlight.hubs && hubSet[i]) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, (drawR + 6) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#ab47bc';
          ctx.lineWidth = 2.5 / cam.zoom;
          ctx.setLineDash([]);
          ctx.stroke();
        }
        // Analysis: orphan red outline
        if (analysisHighlight.orphans && orphanSet[i]) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, (drawR + 4) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#ef5350';
          ctx.lineWidth = 1.5 / cam.zoom;
          ctx.setLineDash([4 / cam.zoom, 3 / cam.zoom]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // Analysis: domain edge highlighting
      if (analysisHighlight.domain && analysisResult) {
        var hlDomain = analysisHighlight.domain;
        var hlInfo = null;
        for (var di = 0; di < analysisResult.domains.length; di++) {
          if (analysisResult.domains[di].name === hlDomain) { hlInfo = analysisResult.domains[di]; break; }
        }
        if (hlInfo) {
          var hlSet = {};
          for (var di = 0; di < hlInfo.nodeIndices.length; di++) hlSet[hlInfo.nodeIndices[di]] = true;
          var hlColor = hlInfo.status === 'healthy' ? 'rgba(102,187,106,0.7)' :
                        hlInfo.status === 'sparse' ? 'rgba(239,83,80,0.7)' : 'rgba(255,167,38,0.7)';
          for (var e = 0; e < edgeIdx.length; e++) {
            if (hlSet[edgeIdx[e].s] && hlSet[edgeIdx[e].t]) {
              var a = nodes[edgeIdx[e].s], b = nodes[edgeIdx[e].t];
              ctx.beginPath();
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(b.x, b.y);
              ctx.strokeStyle = hlColor;
              ctx.lineWidth = 2.5 / cam.zoom;
              ctx.stroke();
            }
          }
        }
      }

      // Labels
      var labelThreshold = cam.zoom > 1.5 ? 3 : cam.zoom > 0.8 ? 6 : 999;
      ctx.font = Math.max(9, 11 / cam.zoom) + 'px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      for (var i = 0; i < nodes.length; i++) {
        var showByHover = hoverActive && highlightSet[i];
        var showByDomain = !hoverActive && domainActive && domainSet[i];
        var showByDegree = !hasHighlight && nodes[i].degree >= labelThreshold;
        if (!showByHover && !showByDomain && !showByDegree) continue;
        var node = nodes[i];
        var r = nodeRadius(node);
        ctx.fillStyle = 'rgba(232,226,217,0.9)';
        ctx.fillText(node.label, node.x, node.y + r / cam.zoom + 3 / cam.zoom);
      }

      ctx.restore();
    }

    var running = true;
    var frameCount = 0;
    function loop() {
      if (!running) return;
      step();
      frameCount++;
      if (frameCount === 80) fitToView();
      draw();
      requestAnimationFrame(loop);
    }
    loop();

    document.getElementById('graph-reset-btn').onclick = function () {
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].x = W / 2 + (Math.random() - 0.5) * W * 0.6;
        nodes[i].y = H / 2 + (Math.random() - 0.5) * H * 0.6;
        nodes[i].vx = 0;
        nodes[i].vy = 0;
      }
      frameCount = 0;
    };

    // Analysis modal
    var analysisBackdrop = document.getElementById('analysis-backdrop');
    var analysisBody = document.getElementById('analysis-modal-body');

    function closeAnalysis() {
      analysisBackdrop.classList.remove('visible');
      analysisHighlight = { bridges: false, hubs: false, orphans: false, domain: null };
    }

    document.getElementById('analysis-close-btn').addEventListener('click', closeAnalysis);
    analysisBackdrop.addEventListener('click', function (ev) {
      if (ev.target === analysisBackdrop) closeAnalysis();
    });

    function focusNode(idx) {
      cam.x = nodes[idx].x;
      cam.y = nodes[idx].y;
      cam.zoom = 2;
      showPreviewNode(nodes[idx]);
    }

    function fmt(n, d) { return d === undefined ? n.toString() : n.toFixed(d); }

    function populateAnalysis(result) {
      analysisBody.textContent = '';
      if (result.insufficient) {
        var msg = document.createElement('div');
        msg.className = 'analysis-insufficient';
        msg.textContent = 'Insufficient data for analysis (need at least 2 nodes).';
        analysisBody.appendChild(msg);
        return;
      }

      var cards = document.createElement('div');
      cards.className = 'analysis-cards';
      var cardData = [
        { value: fmt(result.sigma, 2), label: '\u03c3 Small-World' },
        { value: fmt(result.avgPathLength, 2), label: 'Avg Path Length' },
        { value: fmt(result.avgClustering, 3), label: 'Avg Clustering' },
        { value: result.nodes, label: 'Nodes' },
        { value: result.edges, label: 'Edges' },
        { value: fmt(result.avgDegree, 1), label: 'Avg Degree' }
      ];
      for (var c = 0; c < cardData.length; c++) {
        var card = document.createElement('div');
        card.className = 'analysis-card';
        var val = document.createElement('div');
        val.className = 'card-value';
        val.textContent = cardData[c].value;
        card.appendChild(val);
        var lbl = document.createElement('div');
        lbl.className = 'card-label';
        lbl.textContent = cardData[c].label;
        card.appendChild(lbl);
        cards.appendChild(card);
      }
      analysisBody.appendChild(cards);

      var interp = document.createElement('p');
      interp.style.fontSize = '0.74rem';
      interp.style.color = 'var(--color-text-secondary)';
      interp.style.margin = '0 0 1rem';
      if (result.sigma > 1) {
        interp.textContent = '\u03c3 > 1: this graph exhibits small-world structure with high clustering and short average paths.';
      } else if (result.sigma > 0) {
        interp.textContent = '\u03c3 < 1: this graph does not show strong small-world properties.';
      } else {
        interp.textContent = '\u03c3 could not be computed (disconnected graph or insufficient edges).';
      }
      analysisBody.appendChild(interp);

      // Domain table
      var domSection = document.createElement('div');
      domSection.className = 'analysis-section';
      var domH = document.createElement('h4');
      domH.textContent = 'Per-Domain Analysis';
      domSection.appendChild(domH);
      var table = document.createElement('table');
      table.className = 'analysis-table';
      appendTableHead(table, ['Domain', 'Nodes', 'Density', 'Cross-Links', 'Clustering', 'Status']);
      var tbody = document.createElement('tbody');
      for (var d = 0; d < result.domains.length; d++) {
        var dom = result.domains[d];
        var tr = document.createElement('tr');
        tr.className = 'clickable';
        var nameCell = document.createElement('td');
        var colorDot = document.createElement('span');
        colorDot.style.display = 'inline-block';
        colorDot.style.width = '8px';
        colorDot.style.height = '8px';
        colorDot.style.borderRadius = '50%';
        colorDot.style.background = DOMAIN_COLORS[dom.name] || DOMAIN_DEFAULT_COLOR;
        colorDot.style.marginRight = '0.4rem';
        colorDot.style.verticalAlign = 'middle';
        nameCell.appendChild(colorDot);
        nameCell.appendChild(document.createTextNode(dom.name));
        tr.appendChild(nameCell);
        tr.appendChild(el('td', String(dom.nodes)));
        tr.appendChild(el('td', fmt(dom.density, 4)));
        tr.appendChild(el('td', String(dom.crossEdges)));
        tr.appendChild(el('td', fmt(dom.clustering, 3)));
        tr.appendChild(makeBadgeCell(dom.status, 'badge-' + dom.status));
        (function (domName) {
          tr.addEventListener('mouseenter', function () {
            analysisHighlight.domain = domName;
          });
          tr.addEventListener('mouseleave', function () {
            analysisHighlight.domain = null;
          });
          tr.addEventListener('click', function () {
            selectedDomain = domName;
            for (var key in legendItems) {
              legendItems[key].classList.remove('active', 'dimmed');
              legendItems[key].classList.add(key === domName ? 'active' : 'dimmed');
            }
          });
        })(dom.name);
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      domSection.appendChild(table);
      analysisBody.appendChild(domSection);

      // Bridges section
      if (result.bridges.length > 0) {
        var bridgeSection = document.createElement('div');
        bridgeSection.className = 'analysis-section';
        var bH = document.createElement('h4');
        bH.textContent = 'Bridge / Bottleneck Nodes (' + result.bridges.length + ')';
        bridgeSection.appendChild(bH);
        var bToggle = document.createElement('label');
        bToggle.style.cssText = 'font-size:0.72rem;cursor:pointer;display:block;margin-bottom:0.4rem;';
        var bCheck = document.createElement('input');
        bCheck.type = 'checkbox';
        bCheck.checked = analysisHighlight.bridges;
        bCheck.addEventListener('change', function () { analysisHighlight.bridges = this.checked; });
        bToggle.appendChild(bCheck);
        bToggle.appendChild(document.createTextNode(' Highlight on graph'));
        bridgeSection.appendChild(bToggle);
        var bTable = document.createElement('table');
        bTable.className = 'analysis-table';
        appendTableHead(bTable, ['Node', 'Domain', 'Betweenness']);
        var bTbody = document.createElement('tbody');
        for (var b = 0; b < result.bridges.length; b++) {
          var br = result.bridges[b];
          var btr = document.createElement('tr');
          btr.className = 'clickable';
          var td1 = document.createElement('td');
          var link = document.createElement('span');
          link.className = 'analysis-node-link';
          link.textContent = br.label;
          link.title = br.id;
          (function (idx) {
            link.addEventListener('click', function (ev) {
              ev.stopPropagation();
              focusNode(idx);
            });
          })(br.index);
          td1.appendChild(link);
          btr.appendChild(td1);
          btr.appendChild(makeBadgeCell(br.domain, 'badge-bridge'));
          btr.appendChild(el('td', fmt(br.betweenness, 1)));
          bTbody.appendChild(btr);
        }
        bTable.appendChild(bTbody);
        bridgeSection.appendChild(bTable);
        analysisBody.appendChild(bridgeSection);
      }

      // Hubs section
      if (result.hubs.length > 0) {
        var hubSection = document.createElement('div');
        hubSection.className = 'analysis-section';
        var hH = document.createElement('h4');
        hH.textContent = 'Hub Nodes (Top ' + result.hubs.length + ' by Degree)';
        hubSection.appendChild(hH);
        var hToggle = document.createElement('label');
        hToggle.style.cssText = 'font-size:0.72rem;cursor:pointer;display:block;margin-bottom:0.4rem;';
        var hCheck = document.createElement('input');
        hCheck.type = 'checkbox';
        hCheck.checked = analysisHighlight.hubs;
        hCheck.addEventListener('change', function () { analysisHighlight.hubs = this.checked; });
        hToggle.appendChild(hCheck);
        hToggle.appendChild(document.createTextNode(' Highlight on graph'));
        hubSection.appendChild(hToggle);
        var hTable = document.createElement('table');
        hTable.className = 'analysis-table';
        appendTableHead(hTable, ['Node', 'Domain', 'Degree']);
        var hTbody = document.createElement('tbody');
        for (var h = 0; h < result.hubs.length; h++) {
          var hub = result.hubs[h];
          var htr = document.createElement('tr');
          htr.className = 'clickable';
          var htd1 = document.createElement('td');
          var hlink = document.createElement('span');
          hlink.className = 'analysis-node-link';
          hlink.textContent = hub.label;
          hlink.title = hub.id;
          (function (idx) {
            hlink.addEventListener('click', function (ev) {
              ev.stopPropagation();
              focusNode(idx);
            });
          })(hub.index);
          htd1.appendChild(hlink);
          htr.appendChild(htd1);
          htr.appendChild(makeBadgeCell(hub.domain, 'badge-hub'));
          htr.appendChild(el('td', String(hub.degree)));
          hTbody.appendChild(htr);
        }
        hTable.appendChild(hTbody);
        hubSection.appendChild(hTable);
        analysisBody.appendChild(hubSection);
      }

      // Orphans section
      if (result.orphans.length > 0) {
        var orphanSection = document.createElement('div');
        orphanSection.className = 'analysis-section';
        var oH = document.createElement('h4');
        oH.textContent = 'Orphan / Weakly-Connected Nodes (' + result.orphans.length + ')';
        orphanSection.appendChild(oH);
        var oToggle = document.createElement('label');
        oToggle.style.cssText = 'font-size:0.72rem;cursor:pointer;display:block;margin-bottom:0.4rem;';
        var oCheck = document.createElement('input');
        oCheck.type = 'checkbox';
        oCheck.checked = analysisHighlight.orphans;
        oCheck.addEventListener('change', function () { analysisHighlight.orphans = this.checked; });
        oToggle.appendChild(oCheck);
        oToggle.appendChild(document.createTextNode(' Highlight on graph'));
        orphanSection.appendChild(oToggle);
        var oList = document.createElement('div');
        oList.style.cssText = 'display:flex;flex-wrap:wrap;gap:0.3rem;';
        for (var o = 0; o < result.orphans.length; o++) {
          var orph = result.orphans[o];
          var chip = document.createElement('span');
          chip.className = 'analysis-node-link';
          chip.style.cssText = 'font-size:0.72rem;padding:0.15rem 0.4rem;background:rgba(130,130,130,0.1);border-radius:3px;';
          chip.textContent = orph.label + (orph.degree === 0 ? ' (isolated)' : ' (deg 1)');
          chip.title = orph.id;
          (function (idx) {
            chip.addEventListener('click', function () { focusNode(idx); });
          })(orph.index);
          oList.appendChild(chip);
        }
        orphanSection.appendChild(oList);
        analysisBody.appendChild(orphanSection);
      }
    }

    document.getElementById('graph-analyze-btn').addEventListener('click', function () {
      analysisResult = analyzeGraph(nodes, graph.edges);
      bridgeSet = {}; hubSet = {}; orphanSet = {};
      if (!analysisResult.insufficient) {
        for (var i = 0; i < analysisResult.bridges.length; i++) bridgeSet[analysisResult.bridges[i].index] = true;
        for (var i = 0; i < analysisResult.hubs.length; i++) hubSet[analysisResult.hubs[i].index] = true;
        for (var i = 0; i < analysisResult.orphans.length; i++) orphanSet[analysisResult.orphans[i].index] = true;
      }
      populateAnalysis(analysisResult);
      renderAccessibleSummary(analysisResult);
      analysisBackdrop.classList.add('visible');
    });

    function onOverlayKeydown(ev) {
      if (ev.key !== 'Escape') return;
      if (analysisBackdrop.classList.contains('visible')) {
        closeAnalysis();
        return;
      }
      closeOverlay();
    }
    overlay.addEventListener('keydown', onOverlayKeydown);

    renderAccessibleSummary(analyzeGraph(nodes, graph.edges));

    graphSim = {
      stop: function () {
        running = false;
        window.removeEventListener('resize', resize);
        overlay.removeEventListener('keydown', onOverlayKeydown);
        closeAnalysis();
      }
    };
  }

  /* ── Public API ──────────────────────────────────────── */

  var graphCache = {};

  function updateGraphScope(scope) {
    var indicator = document.getElementById('graph-scope');
    if (!indicator) return;
    if (scope) {
      indicator.innerHTML = '';
      indicator.appendChild(deps.el('span', '\uD83D\uDCC1 ' + scope));
      var allBtn = deps.el('a', 'show all');
      allBtn.style.marginLeft = '0.5rem';
      allBtn.style.cursor = 'pointer';
      allBtn.addEventListener('click', function () {
        if (graphSim) { graphSim.stop(); graphSim = null; }
        openGraph('');
      });
      indicator.appendChild(allBtn);
      indicator.style.display = '';
    } else {
      indicator.style.display = 'none';
    }
  }

  async function openGraph(scopeOverride) {
    var scope;
    if (typeof scopeOverride === 'string') {
      scope = scopeOverride;
    } else {
      var detailPath = deps.getDetailPath();
      if (detailPath.length > 0) {
        scope = detailPath.join('/');
      } else {
        scope = '';
      }
    }

    var overlay = document.getElementById('graph-overlay');
    overlay.classList.add('visible');

    updateGraphScope(scope);

    if (graphCache[scope]) {
      startGraph(graphCache[scope]);
      return;
    }

    var progress = document.getElementById('graph-progress');
    progress.style.display = '';
    var progressText = document.getElementById('graph-progress-text');

    try {
      var graph = await buildGraph(
        function (msg) { progressText.textContent = msg; },
        scope || undefined
      );
      graphCache[scope] = graph;
      progress.style.display = 'none';
      startGraph(graph);
    } catch (err) {
      progress.style.display = 'none';
      deps.showError('Graph build failed: ' + err.message);
    }
  }

  var api = {
    /** Provide host-page dependencies. Must be called before open(). */
    init: function (config) {
      deps = config;

      if (typeof document === 'undefined') {
        return;
      }

      // Wire up open/close buttons
      document.getElementById('graph-open-btn').addEventListener('click', function () {
        if (!deps.getRootHandle()) {
          deps.showError('No memory repo loaded. Please open the dashboard first.');
          return;
        }
        openGraph();
      });
      document.getElementById('graph-close-btn').addEventListener('click', function () {
        document.getElementById('graph-overlay').classList.remove('visible');
        document.getElementById('graph-preview').classList.remove('visible');
        if (graphSim) { graphSim.stop(); graphSim = null; }
      });
    },

    /** Open the graph (optionally scoped to a domain prefix). */
    open: function (scopeOverride) { return openGraph(scopeOverride); },

    /** Stop the running simulation. */
    stop: function () {
      if (graphSim) { graphSim.stop(); graphSim = null; }
    },

    /** Update the scope indicator in the toolbar. */
    updateScope: updateGraphScope,

    /** Export pure helpers for unit tests. */
    _test: {
      analyzeGraph: analyzeGraph,
      summarizeGraph: summarizeGraph,
      resolveGraphRef: resolveGraphRef,
      extractRefs: extractRefs
    }
  };

  if (root) root.EngramGraph = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
