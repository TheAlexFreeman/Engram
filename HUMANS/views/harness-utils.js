/**
 * harness-utils.js — shared helpers for the harness browser UI.
 *
 * Exposes: window.Harness = { api, fmtDuration, fmtRelative, fmtBytes,
 *   statusBadge, kindStyle, escapeHtml, el, setConnStatus, renderJson }
 *
 * Layered on top of engram-utils.js: we reuse Engram.el / Engram.escapeHtml
 * when present, and fall back to local implementations otherwise.
 */
(function (root) {
  'use strict';

  var E = root.Engram || {};

  function el(tag, text, classes) {
    if (typeof E.el === 'function') return E.el(tag, text, classes);
    var e = document.createElement(tag);
    if (text) e.textContent = text;
    if (classes) e.className = classes;
    return e;
  }

  function escapeHtml(v) {
    if (typeof E.escapeHtml === 'function') return E.escapeHtml(v);
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ── API ────────────────────────────────────────────── */

  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', headers: { 'Accept': 'application/json' } };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body);
    }
    return fetch(path, init).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (t) {
          var err = new Error('HTTP ' + r.status + ': ' + (t || r.statusText));
          err.status = r.status;
          err.body = t;
          throw err;
        });
      }
      var ct = r.headers.get('content-type') || '';
      return ct.indexOf('application/json') === 0 ? r.json() : r.text();
    });
  }

  /* ── Formatting ─────────────────────────────────────── */

  function fmtDuration(ms) {
    if (ms == null || isNaN(ms)) return '—';
    if (ms < 1000) return Math.round(ms) + 'ms';
    if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
    var m = Math.floor(ms / 60000);
    var s = Math.round((ms % 60000) / 1000);
    return m + 'm ' + s + 's';
  }

  function fmtRelative(iso) {
    if (!iso) return '—';
    var t = Date.parse(iso);
    if (isNaN(t)) return iso;
    var delta = Date.now() - t;
    if (delta < 5000) return 'just now';
    if (delta < 60000) return Math.floor(delta / 1000) + 's ago';
    if (delta < 3600000) return Math.floor(delta / 60000) + 'm ago';
    if (delta < 86400000) return Math.floor(delta / 3600000) + 'h ago';
    return Math.floor(delta / 86400000) + 'd ago';
  }

  function fmtBytes(n) {
    if (n == null) return '—';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  /* ── Status pill ────────────────────────────────────── */

  var STATUS_COLORS = {
    running:    { bg: 'rgba(194,180,154,0.18)', fg: '#c2b49a', label: 'running'    },
    done:       { bg: 'rgba(107,202,138,0.15)', fg: '#6bca8a', label: 'done'       },
    error:      { bg: 'rgba(211,95,74,0.18)',  fg: '#d35f4a', label: 'error'      },
    cancelled:  { bg: 'rgba(224,185,78,0.15)', fg: '#e0b94e', label: 'cancelled'  },
    incomplete: { bg: 'rgba(122,112,103,0.25)',fg: '#a89e91', label: 'incomplete' },
    unknown:    { bg: 'rgba(122,112,103,0.25)',fg: '#a89e91', label: 'unknown'    }
  };

  function statusBadge(status) {
    var c = STATUS_COLORS[status] || STATUS_COLORS.unknown;
    var span = el('span', c.label, 'status-pill');
    span.style.background = c.bg;
    span.style.color = c.fg;
    if (status === 'running') span.classList.add('pulse');
    return span;
  }

  /* ── Event kind styling ─────────────────────────────── */

  var KIND_STYLE = {
    session_start:  { color: '#c2b49a', label: 'session_start',  icon: '▶' },
    session_end:    { color: '#a89e91', label: 'session_end',    icon: '■' },
    model_response: { color: '#9ba4cf', label: 'model_response', icon: '🧠' },
    tool_call:      { color: '#0ea5e9', label: 'tool_call',      icon: '⚙' },
    tool_result:    { color: '#6bca8a', label: 'tool_result',    icon: '✓' },
    error:          { color: '#d35f4a', label: 'error',          icon: '!' }
  };
  function kindStyle(kind) { return KIND_STYLE[kind] || { color: '#7a7067', label: kind || '?', icon: '·' }; }

  /* ── Connection status bar ──────────────────────────── */

  function setConnStatus(node, connected, label) {
    if (!node) return;
    node.innerHTML = '';
    var dot = el('span', '', 'dot ' + (connected ? 'connected' : 'disconnected'));
    node.appendChild(dot);
    node.appendChild(document.createTextNode(' ' + (label || (connected ? 'connected' : 'disconnected'))));
  }

  /* ── JSON pretty-printer (no syntax highlighting, just clean indent) ── */

  function renderJson(obj) {
    try {
      return JSON.stringify(obj, null, 2);
    } catch (e) {
      return String(obj);
    }
  }

  root.Harness = {
    api: api,
    fmtDuration: fmtDuration,
    fmtRelative: fmtRelative,
    fmtBytes: fmtBytes,
    statusBadge: statusBadge,
    kindStyle: kindStyle,
    escapeHtml: escapeHtml,
    el: el,
    setConnStatus: setConnStatus,
    renderJson: renderJson,
    STATUS_COLORS: STATUS_COLORS,
    KIND_STYLE: KIND_STYLE
  };
})(window);
