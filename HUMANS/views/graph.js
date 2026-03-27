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
    'ai':                    '#29b6f6',
    'cognitive-science':     '#ab47bc',
    'literature':            '#ff7043',
    'mathematics':           '#26a69a',
    'philosophy':            '#fdd835',
    'rationalist-community': '#ef5350',
    'self':                  '#66bb6a',
    'social-science':        '#ec407a',
    'software-engineering':  '#5c6bc0',
    '_unverified':           '#78909c'
  };
  var DOMAIN_DEFAULT_COLOR = '#888888';

  function parseHexColor(hex) {
    hex = hex.replace('#', '');
    return {
      r: parseInt(hex.substring(0, 2), 16),
      g: parseInt(hex.substring(2, 4), 16),
      b: parseInt(hex.substring(4, 6), 16)
    };
  }
  function lightenColor(hex, amount) {
    var c = parseHexColor(hex);
    return 'rgb(' +
      Math.round(c.r + (255 - c.r) * amount) + ',' +
      Math.round(c.g + (255 - c.g) * amount) + ',' +
      Math.round(c.b + (255 - c.b) * amount) + ')';
  }
  function darkenColor(hex, amount) {
    var c = parseHexColor(hex);
    return 'rgb(' +
      Math.round(c.r * (1 - amount)) + ',' +
      Math.round(c.g * (1 - amount)) + ',' +
      Math.round(c.b * (1 - amount)) + ')';
  }

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
    var topHubs = result.hubs.slice(0, 10).map(function (hub) {
      return {
        id: hub.id,
        label: hub.label,
        domain: hub.domain,
        degree: hub.degree
      };
    });

    var scopeLabel = scope || 'all knowledge domains';
    var TIP_DEGREE    = 'Mean number of links per file. Higher values indicate a more densely interconnected knowledge base.';
    var TIP_PATHLEN   = 'Mean shortest-path distance between any two reachable files. Lower = easier to traverse the full graph.';
    var TIP_CLUSTER   = 'How often a file\'s linked neighbours are also linked to each other (0\u20131). Higher = tighter local clusters.';
    var TIP_SIGMA     = 'Small-world coefficient \u03c3 = (C/C\u2080)\u00a0/\u00a0(L/L\u2080). \u03c3\u00a0>\u00a01 confirms small-world structure.';
    var TIP_SMALLWLD  = 'Small-world graphs combine high local clustering with short global path lengths \u2014 common in real-world knowledge and social networks.';
    var TIP_ORPHAN    = 'Files with zero or one link. They sit outside the main knowledge network and may benefit from cross-references.';

    var sentences = [
      [{ text: 'Scope: ' + scopeLabel + '.' }],
      [
        { text: 'The graph contains ' + result.nodes + ' files and ' + result.edges + ' links, with an ' },
        { text: 'average degree', tip: TIP_DEGREE },
        { text: ' of ' + formatNumber(result.avgDegree, 1) + '.' }
      ],
      [
        { text: 'Average ' },
        { text: 'path length', tip: TIP_PATHLEN },
        { text: ' is ' + formatNumber(result.avgPathLength, 2) + ' and average ' },
        { text: 'clustering', tip: TIP_CLUSTER },
        { text: ' is ' + formatNumber(result.avgClustering, 3) + '.' }
      ],
      result.sigma > 1
        ? [
            { text: 'Small-world', tip: TIP_SMALLWLD },
            { text: ' structure is present with ' },
            { text: '\u03c3', tip: TIP_SIGMA },
            { text: '\u00a0' + formatNumber(result.sigma, 2) + '.' }
          ]
        : (result.sigma > 0
            ? [
                { text: 'Small-world', tip: TIP_SMALLWLD },
                { text: ' structure is weak with ' },
                { text: '\u03c3', tip: TIP_SIGMA },
                { text: '\u00a0' + formatNumber(result.sigma, 2) + '.' }
              ]
            : [
                { text: 'Small-world', tip: TIP_SMALLWLD },
                { text: ' structure could not be computed from the current graph.' }
              ]),
      result.orphans.length > 0
        ? [
            { text: result.orphans.length + ' node' + (result.orphans.length === 1 ? '' : 's') + ' are ' },
            { text: 'isolated or weakly connected', tip: TIP_ORPHAN },
            { text: '.' }
          ]
        : [
            { text: 'No ' },
            { text: 'isolated or weakly connected', tip: TIP_ORPHAN },
            { text: ' nodes were detected.' }
          ]
    ];

    var topBridges = result.bridges.slice(0, 10).map(function (bridge) {
      return { id: bridge.id, label: bridge.label, domain: bridge.domain };
    });

    return {
      title: 'Graph summary for ' + scopeLabel,
      sentences: sentences,
      topDomains: topDomains,
      topHubs: topHubs,
      topBridges: topBridges
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
    var hubs = byDegree.slice(0, 10);

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
      var fname = listing.files[f];
      if (fname === 'NAMES.md' || fname === 'SUMMARY.md') continue;
      if (fname.endsWith('.md')) {
        var segments = prefix.split('/').filter(Boolean);
        var kbParts = knowledgeBase.split('/');
        var relSegments = segments.slice(kbParts.length);
        results.push({
          path: (relSegments.length ? relSegments.join('/') + '/' : '') + fname,
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
    var listenerDisposers = [];
    var previewRequestToken = 0;
    var connectionsRequestToken = 0;

    function registerListener(target, type, handler, options) {
      if (!target || typeof target.addEventListener !== 'function' || typeof target.removeEventListener !== 'function') {
        return;
      }
      target.addEventListener(type, handler, options);
      listenerDisposers.push(function () {
        target.removeEventListener(type, handler, options);
      });
    }

    function disposeListeners() {
      while (listenerDisposers.length > 0) {
        var dispose = listenerDisposers.pop();
        try { dispose(); } catch (_) {}
      }
    }

    // Bring-to-front for overlapping left-side panels
    function bringToFront(panel) {
      a11ySummary.style.zIndex = (panel === a11ySummary) ? 4 : 1;
      legend.style.zIndex = (panel === legend) ? 4 : 1;
    }
    registerListener(a11ySummary, 'mousedown', function () { bringToFront(a11ySummary); });
    registerListener(legend, 'mousedown', function () { bringToFront(legend); });

    stats.textContent = graph.nodes.length + ' files \u00B7 ' + graph.edges.length + ' links';
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('tabindex', '0');
    canvas.setAttribute('aria-label', 'Interactive knowledge graph canvas');

    function renderAccessibleSummary(result) {
      if (!a11ySummary) return;
      var wasCollapsed = a11ySummary.classList.contains('collapsed');
      clearNode(a11ySummary);
      var summary = summarizeGraph(result, graph.scope || 'all knowledge domains');
      a11ySummary.setAttribute('aria-label', summary.title);

      // Title row (always visible, acts as collapse toggle)
      var titleRow = document.createElement('div');
      titleRow.className = 'graph-panel-titlerow';
      var titleEl = document.createElement('h3');
      titleEl.textContent = summary.title;
      var titleArrow = document.createElement('span');
      titleArrow.className = 'graph-panel-arrow';
      titleArrow.textContent = wasCollapsed ? '\u25b8' : '\u25be';
      titleRow.appendChild(titleEl);
      titleRow.appendChild(titleArrow);
      a11ySummary.appendChild(titleRow);

      // Collapsible body
      var bodyEl = document.createElement('div');
      bodyEl.className = 'graph-panel-body';
      if (wasCollapsed) bodyEl.style.display = 'none';

      for (var si = 0; si < summary.sentences.length; si++) {
        var p = document.createElement('p');
        var segs = summary.sentences[si];
        for (var sg = 0; sg < segs.length; sg++) {
          if (segs[sg].tip) {
            var abbr = document.createElement('abbr');
            abbr.title = segs[sg].tip;
            abbr.className = 'graph-term';
            abbr.textContent = segs[sg].text;
            p.appendChild(abbr);
          } else {
            p.appendChild(document.createTextNode(segs[sg].text));
          }
        }
        bodyEl.appendChild(p);
      }

      if (summary.topDomains.length > 0) {
        var domainTitle = document.createElement('p');
        domainTitle.className = 'graph-summary-label';
        domainTitle.textContent = 'Largest domains';
        bodyEl.appendChild(domainTitle);

        var domainList = document.createElement('ul');
        for (var di = 0; di < summary.topDomains.length; di++) {
          var domainItem = document.createElement('li');
          var domain = summary.topDomains[di];
          domainItem.textContent = domain.name + ': ' + domain.nodes + ' nodes (' + domain.status + ')';
          domainList.appendChild(domainItem);
        }
        bodyEl.appendChild(domainList);
      }

      if (summary.topHubs.length > 0) {
        var hubTitle = document.createElement('p');
        hubTitle.className = 'graph-summary-label';
        hubTitle.textContent = 'Top hubs';
        bodyEl.appendChild(hubTitle);

        var HUB_VISIBLE = 3;
        var hubList = document.createElement('ul');
        var hubMoreBtn = null;

        function makeHubItem(hub) {
          var hubItem = document.createElement('li');
          var hubLink = document.createElement('button');
          hubLink.className = 'graph-hub-link';
          hubLink.textContent = hub.label;
          var hubMeta = document.createElement('span');
          hubMeta.className = 'graph-hub-meta';
          hubMeta.textContent = ' (' + hub.domain + ', degree ' + hub.degree + ')';
          hubItem.appendChild(hubLink);
          hubItem.appendChild(hubMeta);
          (function (hubId) {
            registerListener(hubLink, 'mouseenter', function () {
              var idx = idxMap[hubId];
              if (idx !== undefined) hoveredNode = idx;
            });
            registerListener(hubLink, 'mouseleave', function () {
              var idx = idxMap[hubId];
              if (hoveredNode === idx) hoveredNode = -1;
            });
            registerListener(hubLink, 'click', function () {
              var idx = idxMap[hubId];
              if (idx !== undefined) showPreviewNode(nodes[idx]);
            });
          })(hub.id);
          return hubItem;
        }

        for (var hi = 0; hi < summary.topHubs.length; hi++) {
          var hubItem = makeHubItem(summary.topHubs[hi]);
          if (hi >= HUB_VISIBLE) hubItem.style.display = 'none';
          hubList.appendChild(hubItem);
        }
        bodyEl.appendChild(hubList);

        if (summary.topHubs.length > HUB_VISIBLE) {
          hubMoreBtn = document.createElement('button');
          hubMoreBtn.className = 'graph-hub-more';
          hubMoreBtn.textContent = '+ ' + (summary.topHubs.length - HUB_VISIBLE) + ' more';
          var hubExpanded = false;
          registerListener(hubMoreBtn, 'click', function () {
            hubExpanded = !hubExpanded;
            var items = hubList.querySelectorAll('li');
            for (var k = HUB_VISIBLE; k < items.length; k++) {
              items[k].style.display = hubExpanded ? '' : 'none';
            }
            hubMoreBtn.textContent = hubExpanded
              ? '\u2212 show fewer'
              : '+ ' + (summary.topHubs.length - HUB_VISIBLE) + ' more';
          });
          bodyEl.appendChild(hubMoreBtn);
        }
      }

      if (summary.topBridges.length > 0) {
        var bridgeTitle = document.createElement('p');
        bridgeTitle.className = 'graph-summary-label';
        bridgeTitle.textContent = 'Bridge nodes';
        bodyEl.appendChild(bridgeTitle);

        var BRIDGE_VISIBLE = 3;
        var bridgeList = document.createElement('ul');
        var bridgeMoreBtn = null;

        function makeBridgeItem(bridge) {
          var bridgeItem = document.createElement('li');
          var bridgeLink = document.createElement('button');
          bridgeLink.className = 'graph-hub-link';
          bridgeLink.textContent = bridge.label;
          var bridgeMeta = document.createElement('span');
          bridgeMeta.className = 'graph-hub-meta';
          bridgeMeta.textContent = ' (' + bridge.domain + ')';
          bridgeItem.appendChild(bridgeLink);
          bridgeItem.appendChild(bridgeMeta);
          (function (bridgeId) {
            registerListener(bridgeLink, 'mouseenter', function () {
              var idx = idxMap[bridgeId];
              if (idx !== undefined) hoveredNode = idx;
            });
            registerListener(bridgeLink, 'mouseleave', function () {
              var idx = idxMap[bridgeId];
              if (hoveredNode === idx) hoveredNode = -1;
            });
            registerListener(bridgeLink, 'click', function () {
              var idx = idxMap[bridgeId];
              if (idx !== undefined) showPreviewNode(nodes[idx]);
            });
          })(bridge.id);
          return bridgeItem;
        }

        for (var bi = 0; bi < summary.topBridges.length; bi++) {
          var bridgeItem = makeBridgeItem(summary.topBridges[bi]);
          if (bi >= BRIDGE_VISIBLE) bridgeItem.style.display = 'none';
          bridgeList.appendChild(bridgeItem);
        }
        bodyEl.appendChild(bridgeList);

        if (summary.topBridges.length > BRIDGE_VISIBLE) {
          bridgeMoreBtn = document.createElement('button');
          bridgeMoreBtn.className = 'graph-hub-more';
          bridgeMoreBtn.textContent = '+ ' + (summary.topBridges.length - BRIDGE_VISIBLE) + ' more';
          var bridgeExpanded = false;
          registerListener(bridgeMoreBtn, 'click', function () {
            bridgeExpanded = !bridgeExpanded;
            var items = bridgeList.querySelectorAll('li');
            for (var k = BRIDGE_VISIBLE; k < items.length; k++) {
              items[k].style.display = bridgeExpanded ? '' : 'none';
            }
            bridgeMoreBtn.textContent = bridgeExpanded
              ? '\u2212 show fewer'
              : '+ ' + (summary.topBridges.length - BRIDGE_VISIBLE) + ' more';
          });
          bodyEl.appendChild(bridgeMoreBtn);
        }
      } else {
        var noBridgeP = document.createElement('p');
        noBridgeP.textContent = 'No strong bridge nodes were detected.';
        bodyEl.appendChild(noBridgeP);
      }

      a11ySummary.appendChild(bodyEl);

      registerListener(titleRow, 'click', function () {
        var collapsed = a11ySummary.classList.toggle('collapsed');
        bodyEl.style.display = collapsed ? 'none' : '';
        titleArrow.textContent = collapsed ? '\u25b8' : '\u25be';
        bringToFront(a11ySummary);
      });
    }

    function resize() {
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    }
    resize();
    registerListener(window, 'resize', resize);

    // Build legend (clickable domain filter)
    legend.textContent = '';
    var ltitle = el('div', 'Domains', 'legend-title');
    var lArrow = el('span', '\u25be', 'graph-panel-arrow');
    ltitle.appendChild(lArrow);
    legend.appendChild(ltitle);
    var legendItemsWrap = el('div', '', 'legend-items');
    legend.appendChild(legendItemsWrap);
    var domainsSeen = {};
    for (var i = 0; i < graph.nodes.length; i++) {
      domainsSeen[graph.nodes[i].domain] = true;
    }
    var domainOrder = Object.keys(DOMAIN_COLORS);
    var sortedDomains = Object.keys(domainsSeen).sort(function (left, right) {
      var leftIndex = domainOrder.indexOf(left);
      var rightIndex = domainOrder.indexOf(right);
      if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    });
    var selectedDomain = null;
    var hoveredLegendDomain = null;
    var legendItems = {};
    for (var di = 0; di < sortedDomains.length; di++) {
      var d = sortedDomains[di];
      var item = el('div', '', 'legend-item');
      var dot = el('span', '', 'legend-dot');
      dot.style.background = DOMAIN_COLORS[d] || DOMAIN_DEFAULT_COLOR;
      item.appendChild(dot);
      item.appendChild(el('span', d));
      item.dataset.domain = d;
      legendItems[d] = item;
      (function (domain, itemEl) {
        registerListener(itemEl, 'click', function () {
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
        registerListener(itemEl, 'mouseenter', function () {
          hoveredLegendDomain = domain;
        });
        registerListener(itemEl, 'mouseleave', function () {
          if (hoveredLegendDomain === domain) hoveredLegendDomain = null;
        });
      })(d, item);
      legendItemsWrap.appendChild(item);
    }
    var legendCollapsed = false;
    registerListener(ltitle, 'click', function () {
      legendCollapsed = !legendCollapsed;
      legend.classList.toggle('collapsed', legendCollapsed);
      lArrow.textContent = legendCollapsed ? '\u25b8' : '\u25be';
      bringToFront(legend);
    });

    // Initialize node positions
    var W = canvas.width, H = canvas.height;
    var nodes = graph.nodes;
    var edges = graph.edges;

    var idxMap = {};
    for (var n = 0; n < nodes.length; n++) {
      idxMap[nodes[n].id] = n;
      nodes[n].x = W / 2 + (Math.random() - 0.5) * W * 0.6;
      nodes[n].y = H / 2 + (Math.random() - 0.5) * H * 0.6;
      nodes[n].z = (Math.random() - 0.5) * 2;  // depth layer: -1 (far) to 1 (near)
      nodes[n].targetZ = 0;
      nodes[n].vx = 0;
      nodes[n].vy = 0;
      nodes[n].vz = 0;
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

    // ── 3D perspective state ──────────────────────────
    var depth3d = false;
    var canvasWrap = document.getElementById('graph-canvas-wrap');
    var depthBtn = document.getElementById('graph-3d-btn');

    // 3D rotation angles (radians) — controlled by right-drag / middle-drag
    var rotX = 0, rotY = 0;            // current view rotation
    var rotating = false;
    var rotStart = null, rotStartAngles = null;
    var ROT_SENSITIVITY = 0.005;

    // Precomputed sin/cos (updated each frame in draw)
    var sinRX = 0, cosRX = 1, sinRY = 0, cosRY = 1;
    // Z-front offset: shifts projected z so the nearest node is always at a
    // fixed camera distance, making the graph rotate "in place".
    var zFrontOffset = 0;
    function updateRotTrig() {
      sinRX = Math.sin(rotX); cosRX = Math.cos(rotX);
      sinRY = Math.sin(rotY); cosRY = Math.cos(rotY);
    }

    // Project a node's 3D position (x, y, z) into screen-space 2D
    // z is in [-1, 1]; x/y are world coords. Returns {px, py, scale}.
    function project3D(x, y, z) {
      if (!depth3d) return { px: x, py: y, scale: 1 };
      // Centre the coords around the graph centre for rotation
      var cx = x - W / 2, cy = y - H / 2, cz = z * 200; // scale z into world units
      // Rotate around Y axis (left-right drag)
      var x1 =  cx * cosRY + cz * sinRY;
      var z1 = -cx * sinRY + cz * cosRY;
      // Rotate around X axis (up-down drag)
      var y1 =  cy * cosRX - z1 * sinRX;
      var z2 =  cy * sinRX + z1 * cosRX;
      // Perspective projection (virtual camera distance)
      // Use a large fov relative to the max possible depth after rotation
      var fov = 1600;
      var denom = fov + z2 + zFrontOffset;
      // Clamp near-plane: never let the denominator go below a small positive
      // value. Nodes "behind" the camera are projected as very small/far.
      if (denom < 50) denom = 50;
      var scale = fov / denom;
      return {
        px: x1 * scale + W / 2,
        py: y1 * scale + H / 2,
        scale: scale
      };
    }

    // Compute sphere-surface target z for each node based on radial distance
    // from graph centroid.  Half the nodes go front, half go back.
    function computeSphereTargets() {
      var cx = 0, cy = 0;
      for (var i = 0; i < nodes.length; i++) { cx += nodes[i].x; cy += nodes[i].y; }
      cx /= nodes.length || 1;
      cy /= nodes.length || 1;

      // Collect radial distances
      var dists = [];
      for (var i = 0; i < nodes.length; i++) {
        var dx = nodes[i].x - cx, dy = nodes[i].y - cy;
        dists.push(Math.sqrt(dx * dx + dy * dy));
      }
      // Use 85th-percentile distance as the sphere radius so outliers aren't
      // forced flat.  Fall back to 1 to avoid division by zero.
      var sorted = dists.slice().sort(function (a, b) { return a - b; });
      var R = sorted[Math.floor(sorted.length * 0.85)] || 1;

      for (var i = 0; i < nodes.length; i++) {
        var d = Math.min(dists[i] / R, 1);          // normalised, capped at 1
        var zMag = Math.sqrt(1 - d * d);             // sphere surface
        // Deterministic hemisphere: even index → front, odd → back
        nodes[i].targetZ = (i % 2 === 0 ? 1 : -1) * zMag;
      }
    }

    function toggle3D(on) {
      depth3d = typeof on === 'boolean' ? on : !depth3d;
      canvasWrap.classList.toggle('perspective-3d', depth3d);
      depthBtn.classList.toggle('active', depth3d);
      if (depth3d) {
        computeSphereTargets();
      } else {
        // Flatten: targets go to zero, rotation resets
        for (var i = 0; i < nodes.length; i++) nodes[i].targetZ = 0;
        rotX = 0; rotY = 0;
        canvas.style.transform = '';
      }
    }
    registerListener(depthBtn, 'click', function () { toggle3D(); });

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
      cam.zoom = Math.max(0.02, cam.zoom);
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
        var nx = nodes[i].x, ny = nodes[i].y;
        if (depth3d && nodes[i]._px !== undefined) {
          nx = nodes[i]._px; ny = nodes[i]._py;
          r = r * nodes[i]._ps;
        }
        var dx = nx - wx, dy = ny - wy;
        if (dx * dx + dy * dy < (r + pad) * (r + pad)) return i;
      }
      return -1;
    }

    function nodeRadius(node) {
      return Math.min(3 + node.degree * 1.2, 18);
    }

    // Interaction
    registerListener(canvas, 'mousedown', function (ev) {
      // Right-click or middle-click: start 3D rotation
      if (depth3d && (ev.button === 2 || ev.button === 1)) {
        ev.preventDefault();
        rotating = true;
        rotStart = { x: ev.clientX, y: ev.clientY };
        rotStartAngles = { x: rotX, y: rotY };
        canvas.style.cursor = 'move';
        return;
      }
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

    registerListener(canvas, 'contextmenu', function (ev) {
      if (depth3d) ev.preventDefault();
    });

    registerListener(canvas, 'mousemove', function (ev) {
      if (rotating) {
        var dx = ev.clientX - rotStart.x;
        var dy = ev.clientY - rotStart.y;
        rotY = rotStartAngles.y + dx * ROT_SENSITIVITY;
        rotX = rotStartAngles.x + dy * ROT_SENSITIVITY;
        return;
      }
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
      canvas.style.cursor = hit >= 0 ? 'pointer' : (depth3d ? 'grab' : 'grab');

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

    registerListener(canvas, 'mouseup', function () {
      if (rotating) {
        rotating = false;
        canvas.style.cursor = 'grab';
        return;
      }
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
    var previewNodeIdx = -1;

    function closePreview() {
      preview.classList.remove('visible');
      previewNodeId = null;
      previewNodeIdx = -1;
      previewOpenTargetId = null;
      previewRequestToken++;
      connectionsRequestToken++;
    }

    function closeOverlay() {
      closePreview();
      closeAnalysis();
      overlay.classList.remove('visible');
      if (graphSim) { graphSim.stop(); graphSim = null; }
    }

    // Resize handle
    var resizing = false, startX = 0, startW = 0;
    registerListener(previewResize, 'mousedown', function (ev) {
      ev.preventDefault(); ev.stopPropagation();
      resizing = true; startX = ev.clientX;
      startW = preview.offsetWidth;
      previewResize.classList.add('active');
    });
    registerListener(window, 'mousemove', function (ev) {
      if (!resizing) return;
      var newW = Math.max(220, Math.min(startW + (startX - ev.clientX), preview.parentElement.offsetWidth - 60));
      preview.style.width = newW + 'px';
    });
    registerListener(window, 'mouseup', function () {
      if (resizing) { resizing = false; previewResize.classList.remove('active'); }
    });

    registerListener(previewClose, 'click', closePreview);

    async function showPreviewNode(node) {
      var requestToken = ++previewRequestToken;
      previewNodeId = node.id;
      previewNodeIdx = idxMap[node.id] !== undefined ? idxMap[node.id] : -1;

      previewTitle.textContent = node.label;
      previewMeta.textContent = '';
      previewMeta.style.display = 'none';
      previewBody.textContent = 'Loading\u2026';
      preview.classList.add('visible');

      // Reset to content tab for new node, but keep connections tab visible
      if (typeof switchPreviewTab === 'function') switchPreviewTab(activePreviewTab || 'content');

      previewOpenTargetId = node.id;

      var knowledgeBase = deps.getKnowledgeBase();
      var rootHandle = deps.getRootHandle();
      var content = await deps.readFile(rootHandle, knowledgeBase + '/' + node.id);
      if (previewNodeId !== node.id || requestToken !== previewRequestToken) return;

      if (!content) {
        previewBody.textContent = 'Could not read file.';
        return;
      }

      var parsed = deps.parseFrontmatter(content);
      if (previewNodeId !== node.id || requestToken !== previewRequestToken) return;

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
      if (previewNodeId !== node.id || requestToken !== previewRequestToken) return;

      // If connections tab is active, load connections for this node
      if (activePreviewTab === 'connections') renderConnections(node.id);
    }

    var previewOpenTargetId = null;
    registerListener(previewOpen, 'click', function () {
      if (!previewOpenTargetId) return;
      var segs = previewOpenTargetId.split('/');
      var file = segs.pop();
      deps.setDetailPath(segs);
      closePreview();
      document.getElementById('graph-overlay').classList.remove('visible');
      if (graphSim) { graphSim.stop(); graphSim = null; }
      deps.showDetailView();
      deps.viewFile(file);
    });

    /* ── Preview panel tabs (Content / Connections) ───── */

    var previewTabs = document.querySelectorAll('.preview-tab');
    var connectionsPane = document.getElementById('graph-preview-connections');
    var activePreviewTab = 'content';

    function switchPreviewTab(tab) {
      activePreviewTab = tab;
      for (var t = 0; t < previewTabs.length; t++) {
        previewTabs[t].classList.toggle('active', previewTabs[t].dataset.tab === tab);
      }
      previewBody.style.display = tab === 'content' ? '' : 'none';
      previewMeta.style.display = tab === 'content' ? '' : 'none';
      connectionsPane.style.display = tab === 'connections' ? '' : 'none';
      if (tab === 'connections' && previewNodeId) {
        renderConnections(previewNodeId);
      }
    }

    for (var ti = 0; ti < previewTabs.length; ti++) {
      (function (btn) {
        registerListener(btn, 'click', function () { switchPreviewTab(btn.dataset.tab); });
      })(previewTabs[ti]);
    }

    /* ── Connection panel logic ───────────────────────── */

    var connOutbound = document.getElementById('connections-outbound');
    var connInbound = document.getElementById('connections-inbound');
    var connInboundWrap = document.getElementById('connections-inbound-wrap');
    var connSearch = document.getElementById('connections-search');
    var connDropdown = document.getElementById('connection-dropdown');
    var writePermissionGranted = false;

    function domainDot(domain) {
      var dot = document.createElement('span');
      dot.className = 'conn-domain-dot';
      dot.style.background = DOMAIN_COLORS[domain] || DOMAIN_DEFAULT_COLOR;
      return dot;
    }

    async function ensureWritePermission() {
      if (writePermissionGranted) return true;
      var handle = deps.getRootHandle();
      if (!handle || typeof deps.requestWritePermission !== 'function') return false;
      var result = await deps.requestWritePermission(handle);
      if (result === 'granted') { writePermissionGranted = true; return true; }
      return false;
    }

    function showToast(msg, isError) {
      var toast = document.createElement('div');
      toast.className = 'graph-toast' + (isError ? ' graph-toast-error' : '');
      toast.textContent = msg;
      var container = document.getElementById('graph-overlay');
      container.appendChild(toast);
      setTimeout(function () { toast.classList.add('visible'); }, 10);
      setTimeout(function () {
        toast.classList.remove('visible');
        setTimeout(function () { container.removeChild(toast); }, 300);
      }, 2500);
    }

    function rebuildAdj() {
      for (var key in adj) delete adj[key];
      for (var e = 0; e < edges.length; e++) {
        var si = idxMap[edges[e].source], ti = idxMap[edges[e].target];
        if (si === undefined || ti === undefined) continue;
        if (!adj[si]) adj[si] = [];
        if (!adj[ti]) adj[ti] = [];
        adj[si].push(ti);
        adj[ti].push(si);
      }
      // Rebuild edgeIdx
      edgeIdx.length = 0;
      for (var e = 0; e < edges.length; e++) {
        edgeIdx.push({ s: idxMap[edges[e].source], t: idxMap[edges[e].target] });
      }
    }

    function makeConnectionRow(nodeId, label, domain, provenance, canRemove, sourceId) {
      var row = document.createElement('div');
      row.className = 'connection-row';
      row.appendChild(domainDot(domain));
      var labelSpan = document.createElement('span');
      labelSpan.className = 'conn-label';
      labelSpan.textContent = label;
      labelSpan.title = nodeId;
      row.appendChild(labelSpan);
      var badge = document.createElement('span');
      badge.className = 'connection-badge connection-badge-' + provenance;
      badge.textContent = provenance;
      row.appendChild(badge);
      if (canRemove) {
        var removeBtn = document.createElement('button');
        removeBtn.className = 'conn-remove';
        removeBtn.textContent = '\u00d7';
        removeBtn.title = 'Remove link';
        registerListener(removeBtn, 'click', function (ev) {
          ev.stopPropagation();
          handleRemoveLink(sourceId, nodeId, row);
        });
        row.appendChild(removeBtn);
      }
      registerListener(row, 'click', function () {
        var idx = idxMap[nodeId];
        if (idx !== undefined) {
          cam.x = nodes[idx].x;
          cam.y = nodes[idx].y;
          cam.zoom = 2;
          showPreviewNode(nodes[idx]);
        }
      });
      return row;
    }

    async function handleRemoveLink(sourceId, targetId, rowEl) {
      if (!(await ensureWritePermission())) {
        showToast('Write permission required', true);
        return;
      }
      var knowledgeBase = deps.getKnowledgeBase();
      var rootHandle = deps.getRootHandle();
      var result = await deps.removeRelatedEntry(rootHandle, knowledgeBase + '/' + sourceId, targetId);
      if (!result.success) {
        showToast('Failed to remove link', true);
        return;
      }
      // Update graph data
      for (var e = edges.length - 1; e >= 0; e--) {
        if (edges[e].source === sourceId && edges[e].target === targetId) {
          edges.splice(e, 1); break;
        }
      }
      var si = idxMap[sourceId], ti = idxMap[targetId];
      if (si !== undefined) nodes[si].refs = Math.max(0, nodes[si].refs - 1);
      if (ti !== undefined) nodes[ti].refBy = Math.max(0, nodes[ti].refBy - 1);
      if (si !== undefined) nodes[si].degree = nodes[si].refs + nodes[si].refBy;
      if (ti !== undefined) nodes[ti].degree = nodes[ti].refs + nodes[ti].refBy;
      rebuildAdj();
      if (rowEl && rowEl.parentNode) rowEl.parentNode.removeChild(rowEl);
      showToast('Link removed');
    }

    async function handleAddLink(sourceId, targetId) {
      if (!(await ensureWritePermission())) {
        showToast('Write permission required', true);
        return false;
      }
      var knowledgeBase = deps.getKnowledgeBase();
      var rootHandle = deps.getRootHandle();
      var result = await deps.addRelatedEntry(rootHandle, knowledgeBase + '/' + sourceId, targetId);
      if (!result.success) {
        showToast('Failed to add link', true);
        return false;
      }
      // Update graph data
      edges.push({ source: sourceId, target: targetId });
      var si = idxMap[sourceId], ti = idxMap[targetId];
      if (si !== undefined) { nodes[si].refs++; nodes[si].degree = nodes[si].refs + nodes[si].refBy; }
      if (ti !== undefined) { nodes[ti].refBy++; nodes[ti].degree = nodes[ti].refs + nodes[ti].refBy; }
      rebuildAdj();
      showToast('Link added');
      return true;
    }

    function renderConnections(nodeId) {
      var requestToken = ++connectionsRequestToken;
      clearNode(connOutbound);
      clearNode(connInbound);
      connInboundWrap.style.display = 'none';
      connSearch.value = '';
      connDropdown.style.display = 'none';

      var idx = idxMap[nodeId];
      if (idx === undefined) return;

      // Determine which targets are in this node's frontmatter related list
      var knowledgeBase = deps.getKnowledgeBase();
      var rootHandle = deps.getRootHandle();
      deps.readFile(rootHandle, knowledgeBase + '/' + nodeId).then(function (content) {
        if (requestToken !== connectionsRequestToken || previewNodeId !== nodeId) return;
        var related = deps.getRelatedList(content || '');
        var relatedSet = {};
        for (var r = 0; r < related.list.length; r++) {
          relatedSet[related.list[r]] = true;
        }

        // Outbound: nodes this file links to (source === nodeId)
        var outTargets = {};
        var inSources = {};
        for (var e = 0; e < edges.length; e++) {
          if (edges[e].source === nodeId) outTargets[edges[e].target] = true;
          if (edges[e].target === nodeId) inSources[edges[e].source] = true;
        }

        // Render outbound connections
        for (var tid in outTargets) {
          var ti = idxMap[tid];
          if (ti === undefined) continue;
          var tNode = nodes[ti];
          var isFm = !!relatedSet[tid];
          var row = makeConnectionRow(tid, tNode.label, tNode.domain,
            isFm ? 'frontmatter' : 'body', isFm, nodeId);
          connOutbound.appendChild(row);
        }

        // Render inbound connections (only those not already in outbound)
        var hasInbound = false;
        for (var sid in inSources) {
          if (outTargets[sid]) continue;
          var si = idxMap[sid];
          if (si === undefined) continue;
          var sNode = nodes[si];
          var row = makeConnectionRow(sid, sNode.label, sNode.domain, 'inbound', false, sid);
          connInbound.appendChild(row);
          hasInbound = true;
        }
        if (hasInbound) connInboundWrap.style.display = '';

        if (connOutbound.children.length === 0 && !hasInbound) {
          connOutbound.appendChild(el('div', 'No connections found.', 'connections-empty'));
        }
      });
    }

    // Add-link search
    var searchDebounce = null;
    registerListener(connSearch, 'input', function () {
      clearTimeout(searchDebounce);
      var q = connSearch.value.trim().toLowerCase();
      if (q.length < 2) { connDropdown.style.display = 'none'; return; }
      var searchNodeId = previewNodeId;
      searchDebounce = setTimeout(function () {
        if (searchNodeId !== previewNodeId) return;
        clearNode(connDropdown);
        var currentAdj = adj[idxMap[previewNodeId]] || [];
        var connectedSet = {};
        for (var c = 0; c < currentAdj.length; c++) connectedSet[currentAdj[c]] = true;

        var matches = 0;
        for (var n = 0; n < nodes.length; n++) {
          if (nodes[n].id === previewNodeId) continue;
          if (connectedSet[n]) continue;
          if (nodes[n].label.toLowerCase().indexOf(q) < 0 &&
              nodes[n].id.toLowerCase().indexOf(q) < 0) continue;
          var item = document.createElement('div');
          item.className = 'connection-dropdown-item';
          item.appendChild(domainDot(nodes[n].domain));
          var lbl = el('span', nodes[n].label);
          lbl.title = nodes[n].id;
          item.appendChild(lbl);
          (function (targetNode) {
            registerListener(item, 'click', function () {
              connDropdown.style.display = 'none';
              connSearch.value = '';
              var sourceId = previewNodeId;
              handleAddLink(sourceId, targetNode.id).then(function (ok) {
                if (ok && sourceId === previewNodeId) renderConnections(sourceId);
              });
            });
          })(nodes[n]);
          connDropdown.appendChild(item);
          matches++;
          if (matches >= 8) break;
        }
        connDropdown.style.display = matches > 0 ? '' : 'none';
      }, 150);
    });

    registerListener(connSearch, 'blur', function () {
      setTimeout(function () { connDropdown.style.display = 'none'; }, 200);
    });

    registerListener(canvas, 'dblclick', function (ev) {
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      if (hit < 0) { closePreview(); return; }
      showPreviewNode(nodes[hit]);
    });

    registerListener(canvas, 'click', function (ev) {
      if (!preview.classList.contains('visible')) return;
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
      var w = screenToWorld(sx, sy);
      var hit = nodeAt(w.x, w.y);
      if (hit < 0 || nodes[hit].id === previewNodeId) return;
      showPreviewNode(nodes[hit]);
    });

    registerListener(canvas, 'wheel', function (ev) {
      ev.preventDefault();
      var rect = canvas.getBoundingClientRect();
      var sx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      var sy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      var wx = (sx - canvas.width / 2) / cam.zoom + cam.x;
      var wy = (sy - canvas.height / 2) / cam.zoom + cam.y;
      var factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
      var newZoom = Math.max(0.02, Math.min(8, cam.zoom * factor));
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
      var zDamping = 0.92;
      var zDrift = 0.0003;  // gentle z drift for ambient motion

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

        // Spring z toward sphere-surface target (or 0 when flattening)
        if (depth3d || Math.abs(nodes[i].z) > 0.001) {
          var tz = nodes[i].targetZ || 0;
          nodes[i].vz += (tz - nodes[i].z) * 0.04;   // spring toward target
          nodes[i].vz += (Math.random() - 0.5) * zDrift; // tiny ambient jitter
          nodes[i].vz *= zDamping;
          nodes[i].z += nodes[i].vz;
          nodes[i].z = Math.max(-1, Math.min(1, nodes[i].z));
        }
      }
    }

    // Render
    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.scale(cam.zoom, cam.zoom);
      ctx.translate(-cam.x, -cam.y);

      // Update 3D rotation trig and z-front offset
      if (depth3d) {
        updateRotTrig();
        // Pre-pass: find the minimum rotated-z across all nodes so we can
        // offset the projection to keep the nearest surface at a fixed depth.
        var minZ2 = Infinity;
        for (var zi = 0; zi < nodes.length; zi++) {
          var zcx = nodes[zi].x - W / 2, zcy = nodes[zi].y - H / 2, zcz = nodes[zi].z * 200;
          var zz1 = -zcx * sinRY + zcz * cosRY;
          var zz2 =  zcy * sinRX + zz1 * cosRX;
          if (zz2 < minZ2) minZ2 = zz2;
        }
        zFrontOffset = -minZ2;
      } else {
        zFrontOffset = 0;
      }

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
      var legendHoverSet = {};
      var legendHoverActive = hoveredLegendDomain !== null;
      if (legendHoverActive) {
        for (var li = 0; li < nodes.length; li++) {
          if (nodes[li].domain === hoveredLegendDomain) legendHoverSet[li] = true;
        }
      }
      var hasHighlight = hoverActive || domainActive || legendHoverActive;

      // Edges
      for (var e = 0; e < edgeIdx.length; e++) {
        var a = nodes[edgeIdx[e].s], b = nodes[edgeIdx[e].t];
        var pa = project3D(a.x, a.y, a.z), pb = project3D(b.x, b.y, b.z);
        var edgeHover = hoverActive && highlightSet[edgeIdx[e].s] && highlightSet[edgeIdx[e].t];
        var edgeDomain = !hoverActive && domainActive && (domainSet[edgeIdx[e].s] || domainSet[edgeIdx[e].t]);
        var highlighted = edgeHover || edgeDomain;
        var edgeDepthAlpha = depth3d ? 0.3 + 0.35 * ((pa.scale + pb.scale) / 2) : 1;
        ctx.beginPath();
        ctx.moveTo(pa.px, pa.py);
        ctx.lineTo(pb.px, pb.py);
        var baseAlpha = highlighted ? 0.6 : 0.1;
        ctx.strokeStyle = 'rgba(194,180,154,' + (baseAlpha * edgeDepthAlpha).toFixed(3) + ')';
        ctx.lineWidth = (highlighted ? 1.5 : 0.5) / cam.zoom;
        ctx.stroke();
      }

      // Nodes — sort back-to-front when in 3D mode for proper layering
      var drawOrder;
      if (depth3d) {
        // Pre-project all nodes
        for (var pi = 0; pi < nodes.length; pi++) {
          var pp = project3D(nodes[pi].x, nodes[pi].y, nodes[pi].z);
          nodes[pi]._px = pp.px; nodes[pi]._py = pp.py; nodes[pi]._ps = pp.scale;
        }
        drawOrder = [];
        for (var di3 = 0; di3 < nodes.length; di3++) drawOrder.push(di3);
        drawOrder.sort(function (a, b) { return nodes[a]._ps - nodes[b]._ps; });
      } else {
        drawOrder = null;
      }
      for (var _di = 0; _di < nodes.length; _di++) {
        var i = drawOrder ? drawOrder[_di] : _di;
        var node = nodes[i];
        var r = nodeRadius(node);
        var color = DOMAIN_COLORS[node.domain] || DOMAIN_DEFAULT_COLOR;
        var matchedLegendHover = legendHoverActive && legendHoverSet[i];
        var dimmedByHover = hoverActive && !highlightSet[i];
        var dimmedByDomain = !hoverActive && domainActive && !domainSet[i];
        var dimmed = dimmedByHover || dimmedByDomain;
        var isExternal = node.external;

        var nx = depth3d ? node._px : node.x;
        var ny = depth3d ? node._py : node.y;
        var nScale = depth3d ? node._ps : 1;

        // 3D depth scaling via perspective projection
        var drawR = r * nScale;
        if (analysisHighlight.hubs && hubSet[i]) drawR = r * nScale * 1.5;
        var depthAlpha = depth3d ? Math.max(0.25, Math.min(1, 0.3 + nScale * 0.7)) : 1;

        if (depth3d) ctx.globalAlpha = depthAlpha;
        ctx.beginPath();
        ctx.arc(nx, ny, drawR / cam.zoom, 0, Math.PI * 2);
        if (isExternal) {
          ctx.fillStyle = 'rgba(60,55,50,0.3)';
          ctx.fill();
          ctx.setLineDash([3 / cam.zoom, 3 / cam.zoom]);
          ctx.strokeStyle = dimmed ? 'rgba(120,115,110,0.3)' : color;
          ctx.lineWidth = 1.5 / cam.zoom;
          ctx.stroke();
          ctx.setLineDash([]);
        } else if (depth3d && !dimmed) {
          // Spherical radial gradient: specular highlight offset up-left
          var screenR = drawR / cam.zoom;
          var grad = ctx.createRadialGradient(
            nx - screenR * 0.3, ny - screenR * 0.35, screenR * 0.1,
            nx, ny, screenR
          );
          grad.addColorStop(0, lightenColor(color, 0.6));
          grad.addColorStop(0.45, color);
          grad.addColorStop(1, darkenColor(color, 0.5));
          ctx.fillStyle = grad;
          ctx.fill();
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

        if (matchedLegendHover && !hoverActive && !domainActive) {
          ctx.beginPath();
          ctx.arc(nx, ny, (drawR + 4.5) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = color;
          ctx.lineWidth = 2 / cam.zoom;
          ctx.globalAlpha = 0.55;
          ctx.setLineDash([]);
          ctx.stroke();
          ctx.globalAlpha = 1;
        }

        // Persistent ring for the node open in the sidebar
        if (i === previewNodeIdx && i !== hoveredNode) {
          ctx.beginPath();
          ctx.arc(nx, ny, (drawR + 3.5) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(255,255,255,0.55)';
          ctx.lineWidth = 1.5 / cam.zoom;
          ctx.setLineDash([4 / cam.zoom, 3 / cam.zoom]);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // Analysis: bridge halo
        if (analysisHighlight.bridges && bridgeSet[i]) {
          ctx.beginPath();
          ctx.arc(nx, ny, (drawR + 5) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#42a5f5';
          ctx.lineWidth = 2 / cam.zoom;
          ctx.setLineDash([]);
          ctx.stroke();
        }
        // Analysis: hub glow
        if (analysisHighlight.hubs && hubSet[i]) {
          ctx.beginPath();
          ctx.arc(nx, ny, (drawR + 6) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#ab47bc';
          ctx.lineWidth = 2.5 / cam.zoom;
          ctx.setLineDash([]);
          ctx.stroke();
        }
        // Analysis: orphan red outline
        if (analysisHighlight.orphans && orphanSet[i]) {
          ctx.beginPath();
          ctx.arc(nx, ny, (drawR + 4) / cam.zoom, 0, Math.PI * 2);
          ctx.strokeStyle = '#ef5350';
          ctx.lineWidth = 1.5 / cam.zoom;
          ctx.setLineDash([4 / cam.zoom, 3 / cam.zoom]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
        if (depth3d) ctx.globalAlpha = 1;
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
              var ha = depth3d ? { px: a._px, py: a._py } : { px: a.x, py: a.y };
              var hb = depth3d ? { px: b._px, py: b._py } : { px: b.x, py: b.y };
              ctx.beginPath();
              ctx.moveTo(ha.px, ha.py);
              ctx.lineTo(hb.px, hb.py);
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
        var showByLegendHover = !hoverActive && legendHoverActive && legendHoverSet[i];
        var showByDegree = !hasHighlight && nodes[i].degree >= labelThreshold;
        var showByPreview = i === previewNodeIdx;
        if (!showByHover && !showByDomain && !showByLegendHover && !showByDegree && !showByPreview) continue;
        var node = nodes[i];
        var r = nodeRadius(node);
        var lnx = depth3d ? node._px : node.x;
        var lny = depth3d ? node._py : node.y;
        var lScale = depth3d ? node._ps : 1;
        var labelAlpha = depth3d ? Math.max(0.2, 0.3 + lScale * 0.6) : 0.9;
        ctx.fillStyle = 'rgba(232,226,217,' + labelAlpha.toFixed(2) + ')';
        ctx.fillText(node.label, lnx, lny + r * lScale / cam.zoom + 3 / cam.zoom);
      }

      ctx.restore();

      // Update rotation indicator
      if (depth3d) {
        var rotHint = document.getElementById('graph-rotation-values');
        if (rotHint) {
          var degX = (rotX * 180 / Math.PI).toFixed(1);
          var degY = (rotY * 180 / Math.PI).toFixed(1);
          rotHint.textContent = 'X ' + degX + '\u00b0  Y ' + degY + '\u00b0';
        }
      }
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

    var graphResetBtn = document.getElementById('graph-reset-btn');
    registerListener(graphResetBtn, 'click', function () {
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].x = W / 2 + (Math.random() - 0.5) * W * 0.6;
        nodes[i].y = H / 2 + (Math.random() - 0.5) * H * 0.6;
        nodes[i].z = depth3d ? (Math.random() - 0.5) * 2 : 0;
        nodes[i].vx = 0;
        nodes[i].vy = 0;
        nodes[i].vz = 0;
        nodes[i].targetZ = 0;
      }
      if (depth3d) computeSphereTargets();
      rotX = 0; rotY = 0;
      frameCount = 0;
    });

    // Analysis modal
    var analysisBackdrop = document.getElementById('analysis-backdrop');
    var analysisBody = document.getElementById('analysis-modal-body');

    function closeAnalysis() {
      analysisBackdrop.classList.remove('visible');
      analysisHighlight = { bridges: false, hubs: false, orphans: false, domain: null };
    }

    registerListener(document.getElementById('analysis-close-btn'), 'click', closeAnalysis);
    registerListener(analysisBackdrop, 'click', function (ev) {
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
          registerListener(tr, 'mouseenter', function () {
            analysisHighlight.domain = domName;
          });
          registerListener(tr, 'mouseleave', function () {
            analysisHighlight.domain = null;
          });
          registerListener(tr, 'click', function () {
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
        registerListener(bCheck, 'change', function () { analysisHighlight.bridges = this.checked; });
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
            registerListener(link, 'click', function (ev) {
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
        registerListener(hCheck, 'change', function () { analysisHighlight.hubs = this.checked; });
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
            registerListener(hlink, 'click', function (ev) {
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
        registerListener(oCheck, 'change', function () { analysisHighlight.orphans = this.checked; });
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
            registerListener(chip, 'click', function () { focusNode(idx); });
          })(orph.index);
          oList.appendChild(chip);
        }
        orphanSection.appendChild(oList);
        analysisBody.appendChild(orphanSection);
      }
    }

    registerListener(document.getElementById('graph-analyze-btn'), 'click', function () {
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

    // ── Keyboard navigation ──────────────────────────
    var PAN_STEP = 30;     // pixels per arrow-key press
    var ROT_STEP = 0.05;   // radians per Ctrl+arrow press

    function onOverlayKeydown(ev) {
      if (ev.key === 'Escape') {
        if (analysisBackdrop.classList.contains('visible')) {
          closeAnalysis();
          return;
        }
        closeOverlay();
        return;
      }

      var isArrow = ev.key === 'ArrowUp' || ev.key === 'ArrowDown' ||
                    ev.key === 'ArrowLeft' || ev.key === 'ArrowRight';
      if (!isArrow) return;
      ev.preventDefault();

      // Ctrl+Arrow in 3D mode → rotate
      if (ev.ctrlKey && depth3d) {
        switch (ev.key) {
          case 'ArrowUp':    rotX -= ROT_STEP; break;
          case 'ArrowDown':  rotX += ROT_STEP; break;
          case 'ArrowLeft':  rotY -= ROT_STEP; break;
          case 'ArrowRight': rotY += ROT_STEP; break;
        }
        return;
      }

      // Plain arrows → pan camera
      var step = PAN_STEP / cam.zoom;
      switch (ev.key) {
        case 'ArrowUp':    cam.y -= step; break;
        case 'ArrowDown':  cam.y += step; break;
        case 'ArrowLeft':  cam.x -= step; break;
        case 'ArrowRight': cam.x += step; break;
      }
    }
    registerListener(overlay, 'keydown', onOverlayKeydown);

    renderAccessibleSummary(analyzeGraph(nodes, graph.edges));

    graphSim = {
      stop: function () {
        running = false;
        toggle3D(false);
        clearTimeout(searchDebounce);
        previewOpenTargetId = null;
        previewRequestToken++;
        connectionsRequestToken++;
        disposeListeners();
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
