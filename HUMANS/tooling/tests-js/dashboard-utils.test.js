const test = require('node:test');
const assert = require('node:assert/strict');

const dashboardUtils = require('../../views/dashboard-utils.js');

test('parseJsonl returns only valid JSON objects from mixed log text', function () {
  const results = dashboardUtils.parseJsonl([
    '{"event":"read","path":"a.md"}',
    'not-json',
    '{"event":"write","path":"b.md"}',
    ''
  ].join('\n'));

  assert.deepEqual(results, [
    { event: 'read', path: 'a.md' },
    { event: 'write', path: 'b.md' }
  ]);
});

test('extractSections groups markdown under second-level headings', function () {
  const sections = dashboardUtils.extractSections([
    '# Title',
    '',
    '## Live themes',
    '- One',
    '- Two',
    '## Recent continuity',
    '- Follow up tomorrow'
  ].join('\n'));

  assert.equal(sections['Live themes'], '- One\n- Two\n');
  assert.equal(sections['Recent continuity'], '- Follow up tomorrow\n');
});

test('parseCurrentStage reads the live stage from core INIT text', function () {
  const stage = dashboardUtils.parseCurrentStage([
    'Some heading',
    '',
    '## Current active stage: Calibration',
    '',
    'More text'
  ].join('\n'));

  assert.equal(stage, 'Calibration');
});

test('parseCurrentStage returns Unknown when the stage marker is absent', function () {
  assert.equal(dashboardUtils.parseCurrentStage('# No active stage here'), 'Unknown');
});