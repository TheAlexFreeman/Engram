/**
 * engram-utils.js — Shared utilities for Engram browser views.
 *
 * Exports via window.Engram:
 *   el, clearNode, escapeHtml, setStatus, makeActivatable, showError, hideError,
 *   readFile, listDir, writeFile,
 *   parseFrontmatter, parseFlatYaml, parseMarkdownTable,
 *   getRelatedList, setRelatedList, addRelatedEntry, removeRelatedEntry,
 *   openDB, loadSavedHandle, saveHandle, clearSavedHandle,
 *   requestReadPermission, requestWritePermission,
 *   restoreSavedHandle, readTextWithFallback,
 *   isGitHubHandle, makeGitHubHandle, detectGitHubRepo,
 *   saveGitHubConfig, loadGitHubConfig, clearGitHubConfig, countFilesGitHub,
 *   buildFileIndex,
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
    if (_isGitHub(dirHandle)) return _readFileGitHub(dirHandle, path);
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
    if (_isGitHub(dirHandle)) return _listDirGitHub(dirHandle, path);
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

  /** Write text content to a file via the File System Access API. Returns true on success. */
  async function writeFile(dirHandle, path, content) {
    if (_isGitHub(dirHandle)) return false;
    var parts = path.split('/').filter(Boolean);
    var current = dirHandle;
    for (var i = 0; i < parts.length - 1; i++) {
      try { current = await current.getDirectoryHandle(parts[i]); }
      catch (_) { return false; }
    }
    try {
      var fh = await current.getFileHandle(parts[parts.length - 1]);
      var writable = await fh.createWritable();
      await writable.write(content);
      await writable.close();
      return true;
    } catch (_) { return false; }
  }

  /* ── GitHub API helpers ────────────────────────────── */

  var GITHUB_CONFIG_KEY = 'engram-github-config';

  function _isGitHub(handle) {
    return handle != null && handle._github === true;
  }

  /** Create a virtual handle that reads from a GitHub repo via API. */
  function makeGitHubHandle(owner, repo, branch) {
    return {
      _github: true,
      owner: String(owner),
      repo: String(repo),
      branch: String(branch || 'main'),
      name: owner + '/' + repo
    };
  }

  /** Auto-detect owner/repo when hosted on GitHub Pages. */
  function detectGitHubRepo() {
    if (typeof location === 'undefined') return null;
    var host = location.hostname || '';
    var m = host.match(/^([a-z0-9_-]+)\.github\.io$/i);
    if (!m) return null;
    var pathParts = location.pathname.split('/').filter(Boolean);
    if (pathParts.length === 0) return null;
    return makeGitHubHandle(m[1], pathParts[0], 'main');
  }

  function saveGitHubConfig(config) {
    if (!config) return;
    try {
      localStorage.setItem(GITHUB_CONFIG_KEY, JSON.stringify({
        owner: config.owner, repo: config.repo, branch: config.branch
      }));
    } catch (_) {}
  }

  function loadGitHubConfig() {
    try {
      var raw = localStorage.getItem(GITHUB_CONFIG_KEY);
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (obj && obj.owner && obj.repo) {
        return makeGitHubHandle(obj.owner, obj.repo, obj.branch);
      }
    } catch (_) {}
    return null;
  }

  function clearGitHubConfig() {
    try { localStorage.removeItem(GITHUB_CONFIG_KEY); } catch (_) {}
  }

  var _ghTreeCache = {};

  async function _fetchGitHubTree(config) {
    var key = config.owner + '/' + config.repo + '/' + config.branch;
    if (_ghTreeCache[key]) return _ghTreeCache[key];
    var url = 'https://api.github.com/repos/' +
      encodeURIComponent(config.owner) + '/' +
      encodeURIComponent(config.repo) + '/git/trees/' +
      encodeURIComponent(config.branch) + '?recursive=1';
    var resp = await fetch(url);
    if (!resp.ok) throw new Error('GitHub API ' + resp.status);
    var data = await resp.json();
    if (!data.tree) throw new Error('No tree data from GitHub');
    _ghTreeCache[key] = data.tree;
    return data.tree;
  }

  async function _readFileGitHub(config, path) {
    var url = 'https://raw.githubusercontent.com/' +
      config.owner + '/' + config.repo + '/' +
      config.branch + '/' + path;
    try {
      var resp = await fetch(url);
      if (!resp.ok) return null;
      return await resp.text();
    } catch (_) { return null; }
  }

  async function _listDirGitHub(config, path) {
    var tree = await _fetchGitHubTree(config);
    var prefix = path ? path.replace(/\/+$/, '') + '/' : '';
    var dirs = [], files = [];
    var seen = {};
    for (var i = 0; i < tree.length; i++) {
      var entry = tree[i];
      if (prefix && !entry.path.startsWith(prefix)) continue;
      var rest = prefix ? entry.path.substring(prefix.length) : entry.path;
      if (!rest) continue;
      var slash = rest.indexOf('/');
      if (slash >= 0) {
        var dirName = rest.substring(0, slash);
        if (!seen['d:' + dirName]) { seen['d:' + dirName] = true; dirs.push(dirName); }
      } else if (entry.type === 'tree') {
        if (!seen['d:' + rest]) { seen['d:' + rest] = true; dirs.push(rest); }
      } else {
        files.push(rest);
      }
    }
    dirs.sort(); files.sort();
    return { dirs: dirs, files: files };
  }

  async function _buildFileIndexGitHub(config, basePath) {
    var tree = await _fetchGitHubTree(config);
    var prefix = basePath ? basePath.replace(/\/+$/, '') + '/' : '';
    var baseParts = basePath ? basePath.split('/').filter(Boolean) : [];
    var results = [];
    for (var i = 0; i < tree.length; i++) {
      var entry = tree[i];
      if (entry.type !== 'blob') continue;
      if (prefix && !entry.path.startsWith(prefix)) continue;
      var fname = entry.path.split('/').pop();
      if (fname === 'NAMES.md' || fname === 'SUMMARY.md') continue;
      if (!fname.endsWith('.md')) continue;
      var entryParts = entry.path.split('/').filter(Boolean);
      var relParts = entryParts.slice(baseParts.length);
      results.push({
        path: relParts.join('/'),
        label: fname.replace(/\.md$/, ''),
        domain: relParts.length > 1 ? relParts[0] : ''
      });
    }
    return results;
  }

  /** Count files under a path using the cached GitHub tree. */
  async function countFilesGitHub(config, path) {
    var tree = await _fetchGitHubTree(config);
    var prefix = path ? path.replace(/\/+$/, '') + '/' : '';
    var count = 0;
    for (var i = 0; i < tree.length; i++) {
      if (tree[i].type === 'blob' && (!prefix || tree[i].path.startsWith(prefix))) count++;
    }
    return count;
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

  /* ── Related-field helpers (frontmatter `related:` manipulation) ── */

  /**
   * Parse the `related:` field from raw file content.
   * Returns { list: string[], format: 'comma'|'yaml-list'|'none' }.
   */
  function getRelatedList(content) {
    var none = { list: [], format: 'none' };
    if (!content) return none;
    var fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!fmMatch) return none;
    var fm = fmMatch[1];

    // YAML list format:  related:\n  - foo.md\n  - bar.md
    var listMatch = fm.match(/^related:\s*\n((?:[ \t]+-\s+.+\n?)+)/m);
    if (listMatch) {
      var items = listMatch[1].match(/^[ \t]+-\s+(.+)/gm);
      var list = [];
      if (items) {
        for (var i = 0; i < items.length; i++) {
          var val = items[i].replace(/^[ \t]+-\s+/, '').trim();
          if (val) list.push(val);
        }
      }
      return { list: list, format: 'yaml-list' };
    }

    // Comma-separated inline format:  related: foo.md, bar.md
    var inlineMatch = fm.match(/^related:\s*(.+)$/m);
    if (inlineMatch) {
      var raw = inlineMatch[1].trim();
      if (!raw) return { list: [], format: 'comma' };
      var parts = raw.split(/,\s*/);
      var list = [];
      for (var i = 0; i < parts.length; i++) {
        var v = parts[i].trim();
        if (v) list.push(v);
      }
      return { list: list, format: 'comma' };
    }

    return none;
  }

  /**
   * Replace or insert the `related:` field in raw file content.
   * Preserves original format when possible. Returns the updated file text.
   */
  function setRelatedList(content, newList, preferFormat) {
    if (!content) content = '';
    var fmMatch = content.match(/^(---\r?\n)([\s\S]*?)(\r?\n---)/);
    var nl = content.indexOf('\r\n') >= 0 ? '\r\n' : '\n';

    // Determine target format
    var current = getRelatedList(content);
    var format = preferFormat || (current.format !== 'none' ? current.format : 'comma');

    // Build the new field text
    var fieldText = '';
    if (newList.length > 0) {
      if (format === 'yaml-list') {
        fieldText = 'related:' + nl;
        for (var i = 0; i < newList.length; i++) {
          fieldText += '  - ' + newList[i] + nl;
        }
        fieldText = fieldText.replace(new RegExp(nl.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + '$'), '');
      } else {
        fieldText = 'related: ' + newList.join(', ');
      }
    }

    if (!fmMatch) {
      // No frontmatter — create one if we have entries to add
      if (newList.length === 0) return content;
      return '---' + nl + fieldText + nl + '---' + nl + content;
    }

    var fm = fmMatch[2];

    // Remove existing related field (both formats)
    var yamlListRx = /^related:\s*\n(?:[ \t]+-\s+.+\n?)*/m;
    var inlineRx = /^related:\s*.*$/m;
    if (yamlListRx.test(fm)) {
      fm = fm.replace(yamlListRx, '');
    } else if (inlineRx.test(fm)) {
      fm = fm.replace(inlineRx, '');
    }

    // Clean up double blank lines from removal
    fm = fm.replace(/\n{3,}/g, '\n\n').replace(/^\n+/, '').replace(/\n+$/, '');

    // Insert new field (or leave it off if empty)
    if (fieldText) {
      fm = fm ? fm + nl + fieldText : fieldText;
    }

    return fmMatch[1] + fm + fmMatch[3] + content.substring(fmMatch[0].length);
  }

  /** Add a related entry to a file. Returns { success: boolean, list: string[] }. */
  async function addRelatedEntry(dirHandle, filePath, targetPath) {
    var content = await readFile(dirHandle, filePath);
    if (content === null) return { success: false, list: [] };
    var rel = getRelatedList(content);
    for (var i = 0; i < rel.list.length; i++) {
      if (rel.list[i] === targetPath) return { success: true, list: rel.list };
    }
    var newList = rel.list.concat([targetPath]);
    var updated = setRelatedList(content, newList);
    var ok = await writeFile(dirHandle, filePath, updated);
    return { success: ok, list: ok ? newList : rel.list };
  }

  /** Remove a related entry from a file. Returns { success: boolean, list: string[] }. */
  async function removeRelatedEntry(dirHandle, filePath, targetPath) {
    var content = await readFile(dirHandle, filePath);
    if (content === null) return { success: false, list: [] };
    var rel = getRelatedList(content);
    var newList = [];
    for (var i = 0; i < rel.list.length; i++) {
      if (rel.list[i] !== targetPath) newList.push(rel.list[i]);
    }
    if (newList.length === rel.list.length) return { success: true, list: rel.list };
    var updated = setRelatedList(content, newList);
    var ok = await writeFile(dirHandle, filePath, updated);
    return { success: ok, list: ok ? newList : rel.list };
  }

  /** Recursively list all .md files under a directory. Returns [{path, label, domain}]. */
  async function buildFileIndex(dirHandle, basePath) {
    if (_isGitHub(dirHandle)) return _buildFileIndexGitHub(dirHandle, basePath);
    var results = [];
    async function walk(handle, prefix) {
      var listing = await listDir(handle, prefix);
      for (var f = 0; f < listing.files.length; f++) {
        var fname = listing.files[f];
        if (fname === 'NAMES.md' || fname === 'SUMMARY.md') continue;
        if (!fname.endsWith('.md')) continue;
        var parts = prefix.split('/').filter(Boolean);
        var baseParts = basePath.split('/').filter(Boolean);
        var relParts = parts.slice(baseParts.length);
        var relPath = (relParts.length ? relParts.join('/') + '/' : '') + fname;
        results.push({
          path: relPath,
          label: fname.replace(/\.md$/, ''),
          domain: relParts[0] || ''
        });
      }
      for (var d = 0; d < listing.dirs.length; d++) {
        var dirName = listing.dirs[d];
        if (dirName === '__pycache__' || dirName.startsWith('.')) continue;
        await walk(handle, prefix ? prefix + '/' + dirName : dirName);
      }
    }
    await walk(dirHandle, basePath);
    return results;
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
    if (_isGitHub(handle)) return 'granted';
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

  /** Request read-write permission on a directory handle. */
  async function requestWritePermission(handle) {
    if (!handle) return 'denied';
    if (_isGitHub(handle)) return 'denied';
    try {
      if (typeof handle.queryPermission === 'function') {
        var current = await handle.queryPermission({ mode: 'readwrite' });
        if (current === 'granted') return current;
      }
      if (typeof handle.requestPermission === 'function') {
        return await handle.requestPermission({ mode: 'readwrite' });
      }
    } catch (_) {
      return 'denied';
    }
    return 'denied';
  }

  async function restoreSavedHandle(opts) {
    opts = opts || {};
    var loadHandle = opts.loadSavedHandle || loadSavedHandle;
    var handle = opts.handle || await loadHandle();
    var status = 'missing';

    if (handle) {
      var permission = await requestReadPermission(handle, {
        mode: opts.mode || 'read',
        prompt: opts.prompt !== false
      });
      if (permission === 'granted') {
        return { status: 'granted', handle: handle };
      }
      status = permission || 'denied';
    }

    // Fallback: try saved GitHub config or auto-detect from GitHub Pages URL
    var gh = loadGitHubConfig() || detectGitHubRepo();
    if (gh) {
      return { status: 'granted', handle: gh, source: 'github' };
    }

    return { status: status, handle: null };
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

  function _decodeFragment(fragment) {
    try {
      return decodeURIComponent(fragment);
    } catch (_) {
      return fragment;
    }
  }

  function normalizeMarkdownAnchor(text) {
    var value = _decodeFragment(String(text == null ? '' : text).trim());
    if (!value) return '';
    return value
      .replace(/^#+/, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[\*_~]+/g, '')
      .toLowerCase()
      .replace(/&(?:amp;)?/g, ' and ')
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/[\s_]+/g, '-')
      .replace(/-+/g, '-');
  }

  function splitMarkdownLinkTarget(target) {
    var raw = String(target == null ? '' : target).trim();
    var hashIndex = raw.indexOf('#');
    var path = hashIndex >= 0 ? raw.substring(0, hashIndex) : raw;
    var fragment = hashIndex >= 0 ? raw.substring(hashIndex + 1) : '';
    return {
      raw: raw,
      path: path,
      fragment: fragment,
      section: fragment ? normalizeMarkdownAnchor(fragment) : ''
    };
  }

  function _findElementById(node, id) {
    if (!node || !id) return null;
    if (node.id === id) return node;

    var children = node.childNodes || [];
    for (var i = 0; i < children.length; i++) {
      var found = _findElementById(children[i], id);
      if (found) return found;
    }
    return null;
  }

  function scrollToMarkdownSection(rootNode, target) {
    var parsed = splitMarkdownLinkTarget(target);
    var sectionId = parsed.section || normalizeMarkdownAnchor(target);
    if (!sectionId) return false;

    var targetNode = _findElementById(rootNode, sectionId);
    if (!targetNode && typeof document !== 'undefined' && document && typeof document.getElementById === 'function') {
      targetNode = document.getElementById(sectionId);
    }
    if (!targetNode) return false;

    if (typeof targetNode.scrollIntoView === 'function') {
      targetNode.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
    if (typeof targetNode.focus === 'function') {
      try {
        targetNode.focus({ preventScroll: true });
      } catch (_) {
        targetNode.focus();
      }
    }
    return true;
  }

  function _nextHeadingId(text, state) {
    var base = normalizeMarkdownAnchor(text) || 'section';
    var counts = state.counts;
    counts[base] = (counts[base] || 0) + 1;
    return counts[base] === 1 ? base : base + '-' + counts[base];
  }

  function _sameOriginMarkdownRef(href) {
    var parsed = splitMarkdownLinkTarget(href);
    return !!parsed.path && parsed.path.match(/\.md$/i) && !parsed.path.match(/^https?:\/\//i);
  }

  function isSafeLinkHref(href) {
    var raw = String(href == null ? '' : href).trim();
    if (!raw) return false;

    // In-document anchors and standard relative paths.
    if (raw.charAt(0) === '#') return true;
    if (raw.startsWith('//')) return false; // protocol-relative URLs are not treated as relative-safe
    if (raw.charAt(0) === '/' || raw.charAt(0) === '?' || raw.startsWith('./') || raw.startsWith('../')) {
      return true;
    }

    var schemeMatch = raw.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/);
    if (!schemeMatch) {
      // Plain relative reference like "docs/page" or "notes.md#section".
      return true;
    }

    var scheme = schemeMatch[1].toLowerCase();
    if (scheme !== 'http' && scheme !== 'https' && scheme !== 'mailto') return false;

    try {
      var parsed = new URL(raw, 'https://engram.local/');
      return parsed.protocol === scheme + ':';
    } catch (_) {
      return false;
    }
  }

  function _makeSectionLink(label, href, opts) {
    var parsed = splitMarkdownLinkTarget(href);
    var a = document.createElement('a');
    a.textContent = label;
    a.href = '#' + parsed.section;
    a.title = href;
    a.addEventListener('click', function (ev) {
      if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
      scrollToMarkdownSection(opts && opts._sectionRoot, href);
    });
    return a;
  }

  function _makeXrefLink(label, href, opts, className) {
    var a = document.createElement('a');
    a.textContent = label;
    a.href = '#';
    a.title = href;
    if (className) a.className = className;
    a.addEventListener('click', function (ev) {
      if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
      if (opts && typeof opts.onXrefClick === 'function') opts.onXrefClick(href);
    });
    return a;
  }

  /* ── Markdown renderer ──────────────────────────────── */

  /**
   * Lightweight markdown-to-DOM renderer.
   * Produces real DOM nodes (no innerHTML). Supports: headings, bold, italic,
  * inline code, links, lists (nested UL/OL), blockquotes, horizontal rules,
  * fenced code blocks, tables, KaTeX math (when loaded), and document
  * section links via generated heading anchors.
   *
   * @param {string} text   Markdown source.
   * @param {Element} container  Target DOM element (will be appended to, NOT cleared).
   * @param {Object} [opts]
   * @param {function(string):void} [opts.onXrefClick]  Called when user clicks an
   *        internal .md cross-reference link. Receives the raw href string.
   */
  function renderMarkdown(text, container, opts) {
    opts = opts || {};
    if (!opts._headingState) opts._headingState = { counts: {} };
    if (!opts._sectionRoot) opts._sectionRoot = container;

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
        h.id = _nextHeadingId(hm[2], opts._headingState);
        h.tabIndex = -1;
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
        if (_sameOriginMarkdownRef(codeText) && onXref) {
          var codeRef = splitMarkdownLinkTarget(codeText);
          var codeLabel = codeRef.path.replace(/\.md$/i, '').split('/').pop();
          if (codeRef.section) codeLabel += ' #' + codeRef.section;
          parent.appendChild(_makeXrefLink(codeLabel, codeText, opts, 'knowledge-xref'));
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
        if (!splitMarkdownLinkTarget(href).path && splitMarkdownLinkTarget(href).section) {
          parent.appendChild(_makeSectionLink(match[5], href, opts));
        } else if (_sameOriginMarkdownRef(href) && onXref) {
          parent.appendChild(_makeXrefLink(match[5], href, opts, 'knowledge-xref'));
        } else if (isSafeLinkHref(href)) {
          var a = document.createElement('a');
          a.textContent = match[5];
          a.href = href;
          if (href.match(/^(https?:|mailto:)/i)) {
            a.rel = 'noopener noreferrer';
            a.target = '_blank';
          }
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
    writeFile: writeFile,
    parseFrontmatter: parseFrontmatter,
    parseFlatYaml: parseFlatYaml,
    parseMarkdownTable: parseMarkdownTable,
    getRelatedList: getRelatedList,
    setRelatedList: setRelatedList,
    addRelatedEntry: addRelatedEntry,
    removeRelatedEntry: removeRelatedEntry,
    buildFileIndex: buildFileIndex,
    normalizeMarkdownAnchor: normalizeMarkdownAnchor,
    splitMarkdownLinkTarget: splitMarkdownLinkTarget,
    isSafeLinkHref: isSafeLinkHref,
    scrollToMarkdownSection: scrollToMarkdownSection,
    openDB: openDB,
    saveHandle: saveHandle,
    loadSavedHandle: loadSavedHandle,
    clearSavedHandle: clearSavedHandle,
    requestReadPermission: requestReadPermission,
    requestWritePermission: requestWritePermission,
    restoreSavedHandle: restoreSavedHandle,
    readTextWithFallback: readTextWithFallback,
    isGitHubHandle: _isGitHub,
    makeGitHubHandle: makeGitHubHandle,
    detectGitHubRepo: detectGitHubRepo,
    saveGitHubConfig: saveGitHubConfig,
    loadGitHubConfig: loadGitHubConfig,
    clearGitHubConfig: clearGitHubConfig,
    countFilesGitHub: countFilesGitHub,
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
