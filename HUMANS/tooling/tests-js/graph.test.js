const test = require('node:test');
const assert = require('node:assert/strict');

const graphApi = require('../../views/graph.js');

const analyzeGraph = graphApi._test.analyzeGraph;
const summarizeGraph = graphApi._test.summarizeGraph;
const resolveGraphRef = graphApi._test.resolveGraphRef;
const extractRefs = graphApi._test.extractRefs;

test('analyzeGraph recognizes a fully connected triangle', function () {
  const nodes = [
    { id: 'a.md', label: 'a', domain: 'ai', degree: 2 },
    { id: 'b.md', label: 'b', domain: 'ai', degree: 2 },
    { id: 'c.md', label: 'c', domain: 'ai', degree: 2 }
  ];
  const edges = [
    { source: 'a.md', target: 'b.md' },
    { source: 'b.md', target: 'c.md' },
    { source: 'c.md', target: 'a.md' }
  ];

  const result = analyzeGraph(nodes, edges);

  assert.equal(result.insufficient, false);
  assert.equal(result.nodes, 3);
  assert.equal(result.edges, 3);
  assert.equal(result.orphans.length, 0);
  assert.equal(result.domains.length, 1);
  assert.equal(result.domains[0].status, 'healthy');
  assert.equal(result.hubs[0].degree, 2);
  assert.ok(result.avgClustering > 0.99);
});

test('analyzeGraph flags weakly connected chain endpoints as orphans', function () {
  const nodes = [
    { id: 'a.md', label: 'a', domain: 'ai', degree: 1 },
    { id: 'b.md', label: 'b', domain: 'ai', degree: 2 },
    { id: 'c.md', label: 'c', domain: 'self', degree: 1 }
  ];
  const edges = [
    { source: 'a.md', target: 'b.md' },
    { source: 'b.md', target: 'c.md' }
  ];

  const result = analyzeGraph(nodes, edges);

  assert.equal(result.insufficient, false);
  assert.equal(result.orphans.length, 2);
  assert.equal(result.hubs[0].label, 'b');
  assert.equal(result.domains.length, 2);
});

test('summarizeGraph produces readable summary data for accessible output', function () {
  const result = {
    insufficient: false,
    nodes: 5,
    edges: 4,
    avgDegree: 1.6,
    avgPathLength: 1.8,
    avgClustering: 0.25,
    sigma: 1.3,
    bridges: [
      { label: 'hub-a' },
      { label: 'hub-b' }
    ],
    orphans: [{ label: 'leaf', degree: 1 }],
    domains: [
      { name: 'ai', nodes: 3, status: 'healthy' },
      { name: 'self', nodes: 2, status: 'sparse' }
    ],
    hubs: [
      { label: 'hub-a', domain: 'ai', degree: 4 },
      { label: 'hub-b', domain: 'self', degree: 2 }
    ]
  };

  const summary = summarizeGraph(result, 'ai');
  const sentenceTexts = summary.sentences.map(function (line) {
    if (typeof line === 'string') return line;
    return line.map(function (segment) { return segment.text; }).join('');
  });

  assert.equal(summary.title, 'Graph summary for ai');
  assert.equal(summary.topDomains.length, 2);
  assert.equal(summary.topHubs[0].label, 'hub-a');
  assert.ok(sentenceTexts.some(function (line) { return line.includes('5 files and 4 links'); }));
  assert.ok(sentenceTexts.some(function (line) { return line.includes('Small-world structure is present'); }));
});

test('resolveGraphRef normalizes relative and bare markdown references', function () {
  assert.equal(
    resolveGraphRef('../mathematics/proof.md', ['ai', 'alignment']),
    'ai/mathematics/proof.md'
  );
  assert.equal(
    resolveGraphRef('./notes/idea', ['self']),
    'self/notes/idea.md'
  );
  assert.equal(
    resolveGraphRef('knowledge/software-engineering/design.md', ['ai']),
    'software-engineering/design.md'
  );
  assert.equal(
    resolveGraphRef('./notes/idea.md#open-questions', ['self']),
    'self/notes/idea.md'
  );
});

test('extractRefs returns related frontmatter, markdown links, and backtick references', function () {
  graphApi.init({
    parseFrontmatter(text) {
      const match = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
      if (!match) return { frontmatter: null, body: text };
      return { frontmatter: match[1], body: match[2] };
    },
    parseFlatYaml(yaml) {
      const result = {};
      yaml.split(/\n/).forEach(function (line) {
        const idx = line.indexOf(':');
        if (idx > -1) result[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
      });
      return result;
    }
  });

  const refs = extractRefs([
    '---',
    'related: notes/a.md, notes/b.md#deep-dive',
    '---',
    'See [doc](../shared/c.md#section) and `inline/ref.md#anchor`.',
    '[external](https://example.com/nope.md)'
  ].join('\n'));

  assert.deepEqual(refs, [
    'notes/a.md',
    'notes/b.md',
    '../shared/c.md',
    'inline/ref.md'
  ]);
});