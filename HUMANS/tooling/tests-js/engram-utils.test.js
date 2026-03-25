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

test('splitMarkdownLinkTarget extracts file path and normalized section slug', function () {
  assert.deepEqual(utils.splitMarkdownLinkTarget('docs/CORE.md#Why YAML instead of markdown'), {
    raw: 'docs/CORE.md#Why YAML instead of markdown',
    path: 'docs/CORE.md',
    fragment: 'Why YAML instead of markdown',
    section: 'why-yaml-instead-of-markdown'
  });

  assert.equal(utils.normalizeMarkdownAnchor('  ## Deep Dive & Scope  '), 'deep-dive-and-scope');
});

function installFakeDom() {
  class FakeTextNode {
    constructor(text) {
      this.nodeType = 3;
      this.parentNode = null;
      this._text = text;
    }

    get textContent() {
      return this._text;
    }

    set textContent(value) {
      this._text = String(value);
    }
  }

  class FakeElement {
    constructor(tagName) {
      this.nodeType = 1;
      this.tagName = tagName.toUpperCase();
      this.childNodes = [];
      this.parentNode = null;
      this.listeners = {};
      this.attributes = {};
      this.className = '';
      this.href = '';
      this.rel = '';
      this.target = '';
      this.title = '';
      this.id = '';
      this.tabIndex = 0;
      this.scrolled = null;
      this.focused = null;
    }

    appendChild(node) {
      this.childNodes.push(node);
      node.parentNode = this;
      return node;
    }

    removeChild(node) {
      const idx = this.childNodes.indexOf(node);
      if (idx >= 0) this.childNodes.splice(idx, 1);
      node.parentNode = null;
      return node;
    }

    addEventListener(type, handler) {
      if (!this.listeners[type]) this.listeners[type] = [];
      this.listeners[type].push(handler);
    }

    setAttribute(name, value) {
      this.attributes[name] = String(value);
      this[name] = String(value);
    }

    scrollIntoView(options) {
      this.scrolled = options;
    }

    focus(options) {
      this.focused = options || true;
    }

    get firstChild() {
      return this.childNodes[0] || null;
    }

    get lastElementChild() {
      for (let i = this.childNodes.length - 1; i >= 0; i -= 1) {
        if (this.childNodes[i].nodeType === 1) return this.childNodes[i];
      }
      return null;
    }

    get textContent() {
      return this.childNodes.map(function (child) { return child.textContent; }).join('');
    }

    set textContent(value) {
      this.childNodes = [];
      if (value) this.appendChild(new FakeTextNode(String(value)));
    }
  }

  function findById(node, id) {
    if (!node) return null;
    if (node.id === id) return node;
    for (const child of node.childNodes || []) {
      const found = findById(child, id);
      if (found) return found;
    }
    return null;
  }

  const roots = [];
  return {
    document: {
      createElement(tagName) {
        const node = new FakeElement(tagName);
        roots.push(node);
        return node;
      },
      createTextNode(text) {
        return new FakeTextNode(text);
      },
      getElementById(id) {
        for (const root of roots) {
          const found = findById(root, id);
          if (found) return found;
        }
        return null;
      }
    }
  };
}

function findElements(node, tagName) {
  const matches = [];
  if (!node) return matches;
  if (node.tagName === tagName.toUpperCase()) matches.push(node);
  for (const child of node.childNodes || []) {
    matches.push.apply(matches, findElements(child, tagName));
  }
  return matches;
}

test('renderMarkdown supports local section links and cross-document anchors', function () {
  const previousDocument = global.document;
  const fakeDom = installFakeDom();
  global.document = fakeDom.document;

  try {
    const container = global.document.createElement('div');
    let clickedRef = null;

    utils.renderMarkdown([
      '[Jump](#Why YAML instead of markdown)',
      '',
      '[Open doc](docs/CORE.md#Deep Dive)',
      '',
      '## Why YAML instead of markdown'
    ].join('\n'), container, {
      onXrefClick(ref) {
        clickedRef = ref;
      }
    });

    const links = findElements(container, 'a');
    const heading = findElements(container, 'h2')[0];

    assert.equal(heading.id, 'why-yaml-instead-of-markdown');

    links[0].listeners.click[0]({ preventDefault() {} });
    assert.deepEqual(heading.scrolled, { block: 'start', behavior: 'smooth' });

    links[1].listeners.click[0]({ preventDefault() {} });
    assert.equal(clickedRef, 'docs/CORE.md#Deep Dive');
  } finally {
    global.document = previousDocument;
  }
});