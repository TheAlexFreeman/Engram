(function (root) {
  'use strict';

  function parseJsonl(text) {
    if (!text) return [];
    var lines = text.split(/\r?\n/).filter(function (line) { return line.trim(); });
    var results = [];
    for (var i = 0; i < lines.length; i++) {
      try {
        results.push(JSON.parse(lines[i]));
      } catch (_) {
        // Ignore malformed log lines so the dashboard can still render partial history.
      }
    }
    return results;
  }

  function extractSections(body) {
    var sections = {};
    var current = null;
    var lines = String(body || '').split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
      var match = lines[i].match(/^##\s+(.+)/);
      if (match) {
        current = match[1].trim();
        sections[current] = '';
      } else if (current !== null) {
        sections[current] += lines[i] + '\n';
      }
    }
    return sections;
  }

  function parseCurrentStage(initText) {
    if (!initText) return 'Unknown';

    var match = String(initText).match(/^## Current active stage:\s*(.+)$/m);
    if (!match) return 'Unknown';

    return match[1].trim() || 'Unknown';
  }

  var api = {
    parseJsonl: parseJsonl,
    extractSections: extractSections,
    parseCurrentStage: parseCurrentStage
  };

  root.EngramDashboard = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
}(typeof window !== 'undefined' ? window : globalThis));