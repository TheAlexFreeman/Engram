/**
 * engram-utils.js — Shared utilities for Engram browser views.
 *
 * Exports via window.Engram:
 *   el, showError, hideError,
 *   readFile, listDir,
 *   parseFrontmatter, parseFlatYaml, parseMarkdownTable,
 *   openDB, loadSavedHandle, saveHandle, clearSavedHandle,
 *   DB_NAME, STORE, HANDLE_KEY
 */
(function () {
  'use strict';

  /* ── DOM helpers ───────────────────────────────────── */

  function el(tag, text, classes) {
    var e = document.createElement(tag);
    if (text) e.textContent = text;
    if (classes) e.className = classes;
    return e;
  }

  function showError(msg) {
    var banner = document.getElementById('error-banner');
    banner.textContent = msg;
    banner.classList.add('visible');
  }

  function hideError() {
    document.getElementById('error-banner').classList.remove('visible');
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

  /* ── public API ────────────────────────────────────── */

  window.Engram = {
    el: el,
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
    DB_NAME: DB_NAME,
    STORE: STORE,
    HANDLE_KEY: HANDLE_KEY
  };
})();
