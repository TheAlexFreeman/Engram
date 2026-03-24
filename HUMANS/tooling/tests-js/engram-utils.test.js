const test = require('node:test');
const assert = require('node:assert/strict');

const utils = require('../../views/engram-utils.js');

test('parseFrontmatter splits YAML header from body', function () {
  const text = ['---', 'title: Test', 'trust: high', '---', '# Heading', 'Body line'].join('\n');
  const parsed = utils.parseFrontmatter(text);

  assert.equal(parsed.frontmatter, 'title: Test\ntrust: high');
  assert.equal(parsed.body, '# Heading\nBody line');
});

test('parseFrontmatter returns raw body when no header exists', function () {
  const parsed = utils.parseFrontmatter('# Heading\nBody');

  assert.equal(parsed.frontmatter, null);
  assert.equal(parsed.body, '# Heading\nBody');
});

test('parseFlatYaml reads flat key value pairs', function () {
  const parsed = utils.parseFlatYaml('trust: high\nsource: docs/setup\nempty:');

  assert.deepEqual(parsed, {
    trust: 'high',
    source: 'docs/setup',
    empty: ''
  });
});

test('parseMarkdownTable maps headers to row values', function () {
  const text = [
    '| File | Purpose |',
    '| --- | --- |',
    '| setup.html | Entry point |',
    '| docs.html | Documentation |'
  ].join('\n');

  assert.deepEqual(utils.parseMarkdownTable(text), [
    { File: 'setup.html', Purpose: 'Entry point' },
    { File: 'docs.html', Purpose: 'Documentation' }
  ]);
});

test('escapeHtml escapes reserved characters without DOM access', function () {
  assert.equal(
    utils.escapeHtml('<tag attr="x">Tom & Jerry\'s</tag>'),
    '&lt;tag attr=&quot;x&quot;&gt;Tom &amp; Jerry&#39;s&lt;/tag&gt;'
  );
});

test('requestReadPermission returns granted without prompting when already allowed', async function () {
  let requested = false;
  const handle = {
    async queryPermission() {
      return 'granted';
    },
    async requestPermission() {
      requested = true;
      return 'granted';
    }
  };

  const perm = await utils.requestReadPermission(handle, { prompt: true });
  assert.equal(perm, 'granted');
  assert.equal(requested, false);
});

test('requestReadPermission prompts when needed and allowed', async function () {
  let requested = false;
  const handle = {
    async queryPermission() {
      return 'prompt';
    },
    async requestPermission() {
      requested = true;
      return 'granted';
    }
  };

  const perm = await utils.requestReadPermission(handle, { prompt: true });
  assert.equal(perm, 'granted');
  assert.equal(requested, true);
});

test('requestReadPermission does not prompt when prompting is disabled', async function () {
  let requested = false;
  const handle = {
    async queryPermission() {
      return 'prompt';
    },
    async requestPermission() {
      requested = true;
      return 'granted';
    }
  };

  const perm = await utils.requestReadPermission(handle, { prompt: false });
  assert.equal(perm, 'prompt');
  assert.equal(requested, false);
});

test('restoreSavedHandle returns missing when no saved handle exists', async function () {
  const restored = await utils.restoreSavedHandle({
    prompt: true,
    loadSavedHandle: async function () {
      return null;
    }
  });

  assert.deepEqual(restored, { status: 'missing', handle: null });
});

test('restoreSavedHandle returns granted handle when permission is available', async function () {
  const handle = {
    async queryPermission() {
      return 'granted';
    }
  };

  const restored = await utils.restoreSavedHandle({ handle: handle, prompt: true });

  assert.equal(restored.status, 'granted');
  assert.equal(restored.handle, handle);
});

test('restoreSavedHandle returns denied when permission is not granted', async function () {
  const handle = {
    async queryPermission() {
      return 'denied';
    }
  };

  const restored = await utils.restoreSavedHandle({ handle: handle, prompt: false });

  assert.deepEqual(restored, { status: 'denied', handle: null });
});

test('makeActivatable wires click and keyboard activation semantics', function () {
  const listeners = {};
  const attrs = {};
  let activations = 0;
  let prevented = false;
  const node = {
    tabIndex: null,
    setAttribute(name, value) {
      attrs[name] = value;
    },
    addEventListener(type, handler) {
      listeners[type] = handler;
    }
  };

  utils.makeActivatable(node, function () {
    activations += 1;
  }, { role: 'link', label: 'Open document' });

  listeners.click({});
  listeners.keydown({ key: 'Enter', preventDefault() { prevented = true; } });

  assert.equal(node.tabIndex, 0);
  assert.equal(attrs.role, 'link');
  assert.equal(attrs['aria-label'], 'Open document');
  assert.equal(activations, 2);
  assert.equal(prevented, true);
});