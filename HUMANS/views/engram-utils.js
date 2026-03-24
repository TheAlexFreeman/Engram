/**
 * engram-utils.js — Shared utilities for Engram browser views.
 *
 * Exports via window.Engram:
 *   el, clearNode, escapeHtml, setStatus, makeActivatable, showError, hideError,
 *   readFile, listDir,
 *   parseFrontmatter, parseFlatYaml, parseMarkdownTable,
 *   openDB, loadSavedHandle, saveHandle, clearSavedHandle,
 *   requestReadPermission, readTextWithFallback,
 *   DB_NAME, STORE, HANDLE_KEY,
 *   renderMarkdown
 */
(function (root) {
  'use strict';

  /* ── DOM helpers ───────────────────────────────────── */

  function el(tag, text, classes) {
    var e = document.createElement(tag);
    if (text) e.textContent = text;
    if (classes) e.className = classes;
    return e;
  }

  function clearNode(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setStatus(bar, connected, text) {
    if (!bar) return;
    clearNode(bar);
    var dot = document.createElement('span');
    dot.className = 'dot ' + (connected ? 'connected' : 'disconnected');
    bar.appendChild(dot);
    bar.appendChild(document.createTextNode(' ' + text));
  }

  function makeActivatable(node, activate, opts) {
    if (!node || typeof activate !== 'function') return node;
    opts = opts || {};

    node.tabIndex = opts.tabIndex !== undefined ? opts.tabIndex : 0;
    if (opts.role !== false) {
      node.setAttribute('role', opts.role || 'button');
    }
    if (opts.label) node.setAttribute('aria-label', opts.label);
    if (opts.current) node.setAttribute('aria-current', opts.current);

    node.addEventListener('click', function (ev) {
      activate(ev);
    });
    node.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar') {
        ev.preventDefault();
        activate(ev);
      }
    });
    return node;
  }

  function showError(msg) {
    var banner = document.getElementById('error-banner');
    if (!banner) return;
    banner.textContent = msg;
    banner.classList.add('visible');
  }

  function hideError() {
    var banner = document.getElementById('error-banner');
    if (!banner) return;
    banner.classList.remove('visible');
  }

  /* ── File System Access helpers ────────────────────── */

  /** Read a text file from a directory handle. Returns null if not found. */
  async function readFile(dirHandle, path) {
    var parts = path.split('/').filter(Boolean);
    var current = dirHandle;
    for (var i = 0; i < parts.length - 1; i++) {
      try { current = await current.getDirectoryHandle(parts[i]); }
      catch (_) { return null; }
    }
    try {
      var fh = await current.getFileHandle(parts[parts.length - 1]);
      var file = await fh.getFile();
      return await file.text();
    } catch (_) { return null; }
  }

  /** List immediate children of a sub-directory. Returns {dirs:[], files:[]}. */
  async function listDir(dirHandle, path) {
    var current = dirHandle;
    if (path) {
      var parts = path.split('/').filter(Boolean);
      for (var i = 0; i < parts.length; i++) {
        try { current = await current.getDirectoryHandle(parts[i]); }
        catch (_) { return { dirs: [], files: [] }; }
      }
    }
    var dirs = [], files = [];
    for await (var entry of current.values()) {
      if (entry.kind === 'directory') dirs.push(entry.name);
      else files.push(entry.name);
    }
    dirs.sort(); files.sort();
    return { dirs: dirs, files: files };
  }

  /* ── Parsing helpers ───────────────────────────────── */

  /** Strip YAML frontmatter and return {frontmatter: string|null, body: string}. */
  function parseFrontmatter(text) {
    if (!text) return { frontmatter: null, body: '' };
    var m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
    if (m) return { frontmatter: m[1], body: m[2] };
    return { frontmatter: null, body: text };
  }

  /** Parse YAML frontmatter into a simple key:value map (flat, string values only). */
  function parseFlatYaml(yamlStr) {
    var obj = {};
    if (!yamlStr) return obj;
    var lines = yamlStr.split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
      var colon = lines[i].indexOf(':');
      if (colon > 0) {
        var key = lines[i].substring(0, colon).trim();
        var val = lines[i].substring(colon + 1).trim();
        obj[key] = val;
      }
    }
    return obj;
  }

  /** Parse a markdown table (simple) into array of row objects. */
  function parseMarkdownTable(text) {
    var lines = text.trim().split(/\r?\n/).filter(function (l) { return l.trim(); });
    if (lines.length < 2) return [];
    var headerIdx = -1;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].indexOf('|') >= 0) { headerIdx = i; break; }
    }
    if (headerIdx < 0) return [];
    var headers = lines[headerIdx].split('|').map(function (c) { return c.trim(); }).filter(Boolean);
    var rows = [];
    for (var j = headerIdx + 2; j < lines.length; j++) {
      if (lines[j].indexOf('|') < 0) break;
      var cells = lines[j].split('|').map(function (c) { return c.trim(); }).filter(Boolean);
      var row = {};
      for (var k = 0; k < headers.length; k++) {
        row[headers[k]] = cells[k] || '';
      }
      rows.push(row);
    }
    return rows;
  }

  /* ── IndexedDB handle persistence ──────────────────── */

  var DB_NAME = 'engram-dashboard';
  var STORE = 'handles';
  var HANDLE_KEY = 'repoRoot';

  function openDB() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  async function saveHandle(handle) {
    try {
      var db = await openDB();
      var tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(handle, HANDLE_KEY);
    } catch (_) { /* IndexedDB unavailable — degrade gracefully */ }
  }

  async function loadSavedHandle() {
    try {
      var db = await openDB();
      return new Promise(function (resolve) {
        var tx = db.transaction(STORE, 'readonly');
        var req = tx.objectStore(STORE).get(HANDLE_KEY);
        req.onsuccess = function () { resolve(req.result || null); };
        req.onerror = function () { resolve(null); };
      });
    } catch (_) { return null; }
  }

  async function clearSavedHandle() {
    try {
      var db = await openDB();
      var tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).delete(HANDLE_KEY);
    } catch (_) {}
  }

  async function requestReadPermission(handle, opts) {
    if (!handle) return 'denied';
    opts = opts || {};
    var mode = opts.mode || 'read';
    var prompt = opts.prompt !== false;

    try {
      if (typeof handle.queryPermission === 'function') {
        var current = await handle.queryPermission({ mode: mode });
        if (current === 'granted' || !prompt) return current;
      }
      if (prompt && typeof handle.requestPermission === 'function') {
        return await handle.requestPermission({ mode: mode });
      }
    } catch (_) {
      return 'denied';
    }

    return 'prompt';
  }

  async function readTextWithFallback(dirHandle, path, fallbackUrl) {
    if (dirHandle) {
      var text = await readFile(dirHandle, path);
      if (text !== null) return text;
    }
    if (!fallbackUrl || typeof fetch !== 'function') return null;
    try {
      var resp = await fetch(fallbackUrl);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return await resp.text();
    } catch (_) {
      return null;
    }
  }

  /* ── Markdown renderer ──────────────────────────────── */

  /**
   * Lightweight markdown-to-DOM renderer.
   * Produces real DOM nodes (no innerHTML). Supports: headings, bold, italic,
   * inline code, links, lists (nested UL/OL), blockquotes, horizontal rules,
   * fenced code blocks, tables, and KaTeX math (when loaded).
   *
   * @param {string} text   Markdown source.
   * @param {Element} container  Target DOM element (will be appended to, NOT cleared).
   * @param {Object} [opts]
   * @param {function(string):void} [opts.onXrefClick]  Called when user clicks an
   *        internal .md cross-reference link. Receives the raw href string.
   */
  function renderMarkdown(text, container, opts) {
    var lines = text.split(/\r?\n/);
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // Blank line — skip
      if (!line.trim()) { i++; continue; }

      // Display math block ($$...$$)
      if (line.match(/^\$\$/)) {
        var mathLines = [];
        if (line.trim() !== '$$') mathLines.push(line.replace(/^\$\$/, ''));
        i++;
        while (i < lines.length && !lines[i].match(/\$\$\s*$/)) {
          mathLines.push(lines[i]); i++;
        }
        if (i < lines.length) {
          var last = lines[i].replace(/\$\$\s*$/, '');
          if (last.trim()) mathLines.push(last);
          i++;
        }
        var mathDiv = document.createElement('div');
        mathDiv.className = 'math-display';
        if (typeof katex !== 'undefined') {
          try {
            katex.render(mathLines.join('\n'), mathDiv, { displayMode: true, throwOnError: false });
          } catch (_) {
            mathDiv.textContent = mathLines.join('\n');
          }
        } else {
          mathDiv.textContent = mathLines.join('\n');
        }
        container.appendChild(mathDiv);
        continue;
      }

      // Fenced code block
      if (line.match(/^```/)) {
        var codeLines = [];
        i++;
        while (i < lines.length && !lines[i].match(/^```/)) {
          codeLines.push(lines[i]); i++;
        }
        i++;
        var pre = document.createElement('pre');
        var code = document.createElement('code');
        code.textContent = codeLines.join('\n');
        pre.appendChild(code);
        container.appendChild(pre);
        continue;
      }

      // Horizontal rule
      if (line.match(/^\s*(-{3,}|\*{3,}|_{3,})\s*$/)) {
        container.appendChild(document.createElement('hr'));
        i++; continue;
      }

      // Heading
      var hm = line.match(/^(#{1,4})\s+(.+)/);
      if (hm) {
        var h = document.createElement('h' + hm[1].length);
        _appendInline(h, hm[2], opts);
        container.appendChild(h);
        i++; continue;
      }

      // Table (line contains | and next line is separator)
      if (line.indexOf('|') >= 0 && i + 1 < lines.length && lines[i + 1].match(/^[\s|:-]+$/)) {
        i = _renderTable(lines, i, container, opts);
        continue;
      }

      // Blockquote
      if (line.match(/^>\s?/)) {
        var bq = document.createElement('blockquote');
        var bqLines = [];
        while (i < lines.length && lines[i].match(/^>\s?/)) {
          bqLines.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        renderMarkdown(bqLines.join('\n'), bq, opts);
        container.appendChild(bq);
        continue;
      }

      // Unordered list
      if (line.match(/^\s*[-*+]\s/)) {
        i = _renderList(lines, i, container, 'ul', opts);
        continue;
      }

      // Ordered list
      if (line.match(/^\s*\d+\.\s/)) {
        i = _renderList(lines, i, container, 'ol', opts);
        continue;
      }

      // Paragraph
      var paraLines = [];
      while (i < lines.length && lines[i].trim() &&
             !lines[i].match(/^(#{1,4}\s|```|>\s?|\s*[-*+]\s|\s*\d+\.\s|\s*(-{3,}|\*{3,}|_{3,})\s*$)/) &&
             !(lines[i].indexOf('|') >= 0 && i + 1 < lines.length && lines[i + 1] && lines[i + 1].match(/^[\s|:-]+$/))) {
        paraLines.push(lines[i]); i++;
      }
      var p = document.createElement('p');
      _appendInline(p, paraLines.join(' '), opts);
      container.appendChild(p);
    }
  }

  function _renderTable(lines, i, container, opts) {
    var headerLine = lines[i];
    var headers = headerLine.split('|').map(function (c) { return c.trim(); }).filter(Boolean);
    i += 2;

    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    for (var h = 0; h < headers.length; h++) {
      var th = document.createElement('th');
      _appendInline(th, headers[h], opts);
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    while (i < lines.length && lines[i].indexOf('|') >= 0 && lines[i].trim()) {
      var cells = lines[i].split('|').map(function (c) { return c.trim(); }).filter(Boolean);
      var tr = document.createElement('tr');
      for (var c = 0; c < headers.length; c++) {
        var td = document.createElement('td');
        _appendInline(td, cells[c] || '', opts);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
      i++;
    }
    table.appendChild(tbody);
    container.appendChild(table);
    return i;
  }

  function _renderList(lines, i, container, tag, opts) {
    var list = document.createElement(tag);
    var pattern = tag === 'ul' ? /^(\s*)[-*+]\s(.*)/ : /^(\s*)\d+\.\s(.*)/;
    var baseIndent = (lines[i].match(/^(\s*)/) || ['', ''])[1].length;

    while (i < lines.length) {
      var m = lines[i].match(pattern);
      if (!m) break;
      var indent = m[1].length;
      if (indent < baseIndent) break;

      if (indent > baseIndent) {
        var lastLi = list.lastElementChild;
        if (lastLi) {
          i = _renderList(lines, i, lastLi, tag, opts);
        } else {
          i++;
        }
        continue;
      }

      var li = document.createElement('li');
      _appendInline(li, m[2], opts);
      list.appendChild(li);
      i++;

      while (i < lines.length && lines[i].trim() && !lines[i].match(pattern) &&
             !lines[i].match(/^\s*(#{1,4}\s|```|>\s?|\s*(-{3,}|\*{3,}|_{3,})\s*$)/) &&
             (lines[i].match(/^\s/) || false)) {
        var contIndent = (lines[i].match(/^(\s*)/) || ['', ''])[1].length;
        if (contIndent <= baseIndent) break;
        li.appendChild(document.createTextNode(' ' + lines[i].trim()));
        i++;
      }
    }
    container.appendChild(list);
    return i;
  }

  function _appendInline(parent, text, opts) {
    if (!text) return;
    var rx = /(\$\$[^$]+\$\$|\$[^$\n]+\$)|(`[^`]+`)|\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\(([^)]+)\)/g;
    var last = 0;
    var match;
    var onXref = opts && opts.onXrefClick;
    while ((match = rx.exec(text)) !== null) {
      if (match.index > last) {
        parent.appendChild(document.createTextNode(text.substring(last, match.index)));
      }
      if (match[1]) {
        // Inline or display math
        var mathSrc = match[1];
        var isDisplay = mathSrc.startsWith('$$');
        var tex = isDisplay ? mathSrc.slice(2, -2) : mathSrc.slice(1, -1);
        var mathEl = document.createElement('span');
        if (typeof katex !== 'undefined') {
          try {
            katex.render(tex, mathEl, { displayMode: isDisplay, throwOnError: false });
          } catch (_) {
            mathEl.textContent = tex;
          }
        } else {
          mathEl.textContent = tex;
        }
        parent.appendChild(mathEl);
      } else if (match[2]) {
        var codeText = match[2].slice(1, -1);
        if (codeText.match(/\.md$/i) && onXref) {
          var xa = document.createElement('a');
          xa.className = 'knowledge-xref';
          xa.textContent = codeText.replace(/\.md$/, '').split('/').pop();
          xa.title = codeText;
          (function (ref) { xa.addEventListener('click', function () { onXref(ref); }); })(codeText);
          parent.appendChild(xa);
        } else {
          var codeEl = document.createElement('code');
          codeEl.textContent = codeText;
          parent.appendChild(codeEl);
        }
      } else if (match[3]) {
        var strong = document.createElement('strong');
        strong.textContent = match[3];
        parent.appendChild(strong);
      } else if (match[4]) {
        var em = document.createElement('em');
        em.textContent = match[4];
        parent.appendChild(em);
      } else if (match[5] && match[6]) {
        var href = match[6];
        if (href.match(/\.md$/i) && !href.match(/^https?:\/\//i) && onXref) {
          var xlink = document.createElement('a');
          xlink.className = 'knowledge-xref';
          xlink.textContent = match[5];
          xlink.title = href;
          (function (ref) { xlink.addEventListener('click', function () { onXref(ref); }); })(href);
          parent.appendChild(xlink);
        } else if (href.match(/^(https?:\/\/|[a-zA-Z0-9]|\.\/)/) && !href.match(/^javascript:/i)) {
          var a = document.createElement('a');
          a.textContent = match[5];
          a.href = href;
          a.rel = 'noopener noreferrer';
          a.target = '_blank';
          parent.appendChild(a);
        } else {
          parent.appendChild(document.createTextNode(match[0]));
        }
      }
      last = match.index + match[0].length;
    }
    if (last < text.length) {
      parent.appendChild(document.createTextNode(text.substring(last)));
    }
  }

  /* ── public API ────────────────────────────────────── */

  var api = {
    el: el,
    clearNode: clearNode,
    escapeHtml: escapeHtml,
    setStatus: setStatus,
    makeActivatable: makeActivatable,
    showError: showError,
    hideError: hideError,
    readFile: readFile,
    listDir: listDir,
    parseFrontmatter: parseFrontmatter,
    parseFlatYaml: parseFlatYaml,
    parseMarkdownTable: parseMarkdownTable,
    openDB: openDB,
    saveHandle: saveHandle,
    loadSavedHandle: loadSavedHandle,
    clearSavedHandle: clearSavedHandle,
    requestReadPermission: requestReadPermission,
    readTextWithFallback: readTextWithFallback,
    DB_NAME: DB_NAME,
    STORE: STORE,
    HANDLE_KEY: HANDLE_KEY,
    renderMarkdown: renderMarkdown
  };

  if (root) root.Engram = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
