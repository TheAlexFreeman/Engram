const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const utils = require('../../views/engram-utils.js');

function readInlineScript(fileName) {
  const htmlPath = path.join(__dirname, '..', '..', 'views', fileName);
  const html = fs.readFileSync(htmlPath, 'utf8');
  const matches = Array.from(html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g));
  if (!matches.length) throw new Error('No inline script found in ' + fileName);
  return matches[matches.length - 1][1];
}

class FakeTextNode {
  constructor(text) {
    this.nodeType = 3;
    this.parentNode = null;
    this._text = String(text);
  }

  get textContent() {
    return this._text;
  }

  set textContent(value) {
    this._text = String(value);
  }
}

class FakeClassList {
  constructor(node) {
    this.node = node;
  }

  add(name) {
    const parts = this.node.className ? this.node.className.split(/\s+/).filter(Boolean) : [];
    if (parts.indexOf(name) === -1) parts.push(name);
    this.node.className = parts.join(' ');
  }

  remove(name) {
    const parts = this.node.className ? this.node.className.split(/\s+/).filter(Boolean) : [];
    this.node.className = parts.filter(function (part) { return part !== name; }).join(' ');
  }

  contains(name) {
    const parts = this.node.className ? this.node.className.split(/\s+/).filter(Boolean) : [];
    return parts.indexOf(name) !== -1;
  }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.nodeType = 1;
    this.tagName = String(tagName).toUpperCase();
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.childNodes = [];
    this.listeners = {};
    this.attributes = {};
    this.style = {};
    this.className = '';
    this.id = '';
    this.href = '';
    this.rel = '';
    this.target = '';
    this.title = '';
    this.tabIndex = 0;
    this.classList = new FakeClassList(this);
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

  dispatch(type, event) {
    const handlers = this.listeners[type] || [];
    for (const handler of handlers) handler(event || { preventDefault() {} });
  }

  setAttribute(name, value) {
    const stringValue = String(value);
    this.attributes[name] = stringValue;
    if (name === 'id') this.id = stringValue;
    else if (name === 'class') this.className = stringValue;
    else this[name] = stringValue;
  }

  get firstChild() {
    return this.childNodes[0] || null;
  }

  get lastChild() {
    return this.childNodes.length ? this.childNodes[this.childNodes.length - 1] : null;
  }

  get lastElementChild() {
    for (let i = this.childNodes.length - 1; i >= 0; i -= 1) {
      if (this.childNodes[i].nodeType === 1) return this.childNodes[i];
    }
    return null;
  }

  get children() {
    return this.childNodes.filter(function (child) { return child.nodeType === 1; });
  }

  get textContent() {
    return this.childNodes.map(function (child) { return child.textContent; }).join('');
  }

  set textContent(value) {
    this.childNodes = [];
    if (value) this.appendChild(new FakeTextNode(String(value)));
  }

  querySelector(selector) {
    return findFirstMatch(this, selector);
  }
}

function elementMatches(node, selector) {
  if (!node || node.nodeType !== 1) return false;
  if (selector.startsWith('#')) return node.id === selector.slice(1);
  if (selector.startsWith('.')) return node.classList.contains(selector.slice(1));

  const parts = selector.split('.');
  const tag = parts[0] ? parts[0].toUpperCase() : '';
  const cls = parts[1] || '';
  if (tag && node.tagName !== tag) return false;
  if (cls && !node.classList.contains(cls)) return false;
  return true;
}

function findFirstMatch(node, selector) {
  for (const child of node.childNodes || []) {
    if (elementMatches(child, selector)) return child;
    const nested = findFirstMatch(child, selector);
    if (nested) return nested;
  }
  return null;
}

function createDocument(elementSpecs) {
  const document = {
    body: null,
    createElement(tagName) {
      return new FakeElement(tagName, document);
    },
    createTextNode(text) {
      return new FakeTextNode(text);
    },
    getElementById(id) {
      if (!document.body) return null;
      if (document.body.id === id) return document.body;
      return findFirstMatch(document.body, '#' + id);
    }
  };

  const body = document.createElement('body');
  document.body = body;
  for (const spec of elementSpecs) {
    const element = document.createElement(spec.tag || 'div');
    element.id = spec.id;
    if (spec.className) element.className = spec.className;
    if (spec.text) element.textContent = spec.text;
    if (spec.style) Object.assign(element.style, spec.style);
    body.appendChild(element);
  }
  return document;
}

function click(node) {
  node.dispatch('click', {
    preventDefault() {}
  });
}

function createEl(document, tag, text, classes) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (classes) node.className = classes;
  return node;
}

function setStatus(document, bar, connected, text) {
  if (!bar) return;
  utils.clearNode(bar);
  const dot = document.createElement('span');
  dot.className = 'dot ' + (connected ? 'connected' : 'disconnected');
  bar.appendChild(dot);
  bar.appendChild(document.createTextNode(' ' + text));
}

async function flush() {
  await Promise.resolve();
  await new Promise(function (resolve) { setImmediate(resolve); });
}

function createBaseContext(document, initialUrl) {
  const window = {
    document: document,
    location: new URL(initialUrl),
    listeners: {},
    addEventListener(type, handler) {
      if (!this.listeners[type]) this.listeners[type] = [];
      this.listeners[type].push(handler);
    }
  };

  const history = {
    pushState(_state, _title, url) {
      window.location = new URL(String(url), window.location.href);
    }
  };

  return {
    window: window,
    document: document,
    history: history,
    URL: URL,
    URLSearchParams: URLSearchParams,
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    Promise: Promise
  };
}

test('docs view smoke: route and xref navigation preserve section anchors', async function () {
  const document = createDocument([
    { id: 'status-bar', tag: 'span' },
    { id: 'open-btn', tag: 'button', style: { display: 'none' } },
    { id: 'error-banner', tag: 'div' },
    { id: 'index-view', tag: 'div' },
    { id: 'doc-cards', tag: 'div' },
    { id: 'reader-view', tag: 'div', style: { display: 'none' } },
    { id: 'reader-breadcrumb', tag: 'div' },
    { id: 'sidebar-list', tag: 'div' },
    { id: 'content-header', tag: 'div' },
    { id: 'content-body', tag: 'div' }
  ]);

  const renderCalls = [];
  const scrollCalls = [];
  const readCalls = [];
  const docs = {
    'QUICKSTART.md': '# Quick Start\n',
    'CORE.md': '# Core\n\nSee [help](HELP.md#Pre-commit failures).',
    'HELP.md': '# Help\n\n## Pre-commit failures\nFix it.'
  };

  const context = createBaseContext(document, 'https://example.test/HUMANS/views/docs.html?doc=CORE.md#why-yaml');
  context.window.Engram = {
    clearNode: utils.clearNode,
    makeActivatable: utils.makeActivatable,
    restoreSavedHandle: async function () { return { status: 'missing', handle: null }; },
    showError: function (msg) { document.getElementById('error-banner').textContent = msg; },
    hideError: function () {},
    splitMarkdownLinkTarget: utils.splitMarkdownLinkTarget,
    scrollToMarkdownSection: function (rootNode, target) {
      scrollCalls.push({ rootNode: rootNode, target: target });
      return true;
    },
    setStatus: function (bar, connected, text) {
      setStatus(document, bar, connected, text);
    },
    parseFrontmatter: utils.parseFrontmatter,
    readTextWithFallback: async function (_rootHandle, filePath) {
      const file = filePath.split('/').pop();
      readCalls.push(file);
      return docs[file] || null;
    },
    renderMarkdown: function (text, body, opts) {
      renderCalls.push({ text: text, body: body, opts: opts });
      body.appendChild(document.createElement('p')).textContent = text;
    }
  };

  const script = readInlineScript('docs.html');
  vm.runInNewContext(script, {
    window: context.window,
    document: context.document,
    history: context.history,
    URL: context.URL,
    URLSearchParams: context.URLSearchParams,
    console: context.console,
    setTimeout: context.setTimeout,
    clearTimeout: context.clearTimeout,
    Promise: context.Promise
  });

  await flush();

  assert.equal(readCalls[0], 'CORE.md');
  assert.equal(document.getElementById('reader-view').style.display, '');
  assert.equal(document.getElementById('index-view').style.display, 'none');
  assert.equal(scrollCalls[0].target, '#why-yaml');

  renderCalls[0].opts.onXrefClick('HELP.md#Pre-commit failures');
  await flush();

  assert.equal(readCalls[1], 'HELP.md');
  assert.equal(scrollCalls[1].target, '#pre-commit-failures');
  assert.match(document.getElementById('content-header').textContent, /Troubleshooting/);
});

test('knowledge view smoke: cross-file section links navigate and scroll to the target section', async function () {
  const document = createDocument([
    { id: 'error-banner', tag: 'div' },
    { id: 'domain-picker', tag: 'div', style: { display: '' } },
    { id: 'placeholder', tag: 'div' },
    { id: 'detail-view', tag: 'div', style: { display: 'none' } },
    { id: 'detail-breadcrumb', tag: 'div' },
    { id: 'sidebar-header', tag: 'div' },
    { id: 'sidebar-list', tag: 'div' },
    { id: 'content-header', tag: 'div' },
    { id: 'content-meta', tag: 'div', style: { display: 'none' } },
    { id: 'content-body', tag: 'div' }
  ]);

  const renderCalls = [];
  const scrollCalls = [];
  const readCalls = [];
  const listCalls = [];
  const files = {
    'core/memory/knowledge/ai/topic.md': '---\nrelated: ../shared/other.md#Section Alpha\n---\n# Topic\n',
    'core/memory/knowledge/shared/other.md': '# Other\n\n## Section Alpha\nTarget\n'
  };

  const listings = {
    'core/memory/knowledge/ai': { dirs: [], files: ['topic.md'] },
    'core/memory/knowledge/shared': { dirs: [], files: ['other.md'] }
  };

  const context = createBaseContext(document, 'https://example.test/HUMANS/views/knowledge.html?domain=ai');
  context.window.showDirectoryPicker = async function () {};
  context.window.Engram = {
    el: function (tag, text, classes) {
      return createEl(document, tag, text, classes);
    },
    showError: function (msg) { document.getElementById('error-banner').textContent = msg; },
    readFile: async function (_rootHandle, filePath) {
      readCalls.push(filePath);
      return Object.prototype.hasOwnProperty.call(files, filePath) ? files[filePath] : null;
    },
    listDir: async function (_rootHandle, dirPath) {
      listCalls.push(dirPath);
      return listings[dirPath] || { dirs: [], files: [] };
    },
    parseFrontmatter: utils.parseFrontmatter,
    parseFlatYaml: utils.parseFlatYaml,
    parseMarkdownTable: utils.parseMarkdownTable,
    restoreSavedHandle: async function () { return { status: 'granted', handle: { name: 'repo' } }; },
    makeActivatable: utils.makeActivatable,
    splitMarkdownLinkTarget: utils.splitMarkdownLinkTarget,
    scrollToMarkdownSection: function (rootNode, target) {
      scrollCalls.push({ rootNode: rootNode, target: target });
      return true;
    },
    renderMarkdown: function (text, body, opts) {
      renderCalls.push({ text: text, body: body, opts: opts });
      body.appendChild(document.createElement('p')).textContent = text;
    }
  };
  context.window.EngramGraph = {
    init: function () {}
  };

  const script = readInlineScript('knowledge.html');
  vm.runInNewContext(script, {
    window: context.window,
    document: context.document,
    history: context.history,
    URL: context.URL,
    URLSearchParams: context.URLSearchParams,
    console: context.console,
    setTimeout: context.setTimeout,
    clearTimeout: context.clearTimeout,
    Promise: context.Promise,
    Engram: context.window.Engram,
    EngramGraph: context.window.EngramGraph
  });

  await flush();
  await flush();

  assert.equal(document.getElementById('detail-view').style.display, '');
  assert.equal(document.getElementById('domain-picker').style.display, 'none');
  assert.equal(listCalls[0], 'core/memory/knowledge/ai');

  const firstFile = document.getElementById('sidebar-list').querySelector('li');
  click(firstFile);
  await flush();

  assert.equal(readCalls[0], 'core/memory/knowledge/ai/topic.md');
  assert.equal(document.getElementById('content-header').textContent, 'topic.md');

  renderCalls[0].opts.onXrefClick('../shared/other.md#Section Alpha');
  await flush();
  await flush();

  assert.equal(readCalls[1], 'core/memory/knowledge/shared/other.md');
  assert.equal(scrollCalls[0].target, '#section-alpha');
  assert.equal(document.getElementById('content-header').textContent, 'other.md');
});