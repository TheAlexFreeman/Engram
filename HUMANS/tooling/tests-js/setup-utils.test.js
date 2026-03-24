const test = require('node:test');
const assert = require('node:assert/strict');

const setupUtils = require('../../views/setup-utils.js');

test('buildGeneratedFiles creates portable Codex config without absolute paths', function () {
  const result = setupUtils.buildGeneratedFiles({
    selectedPlatform: 'codex',
    codexPortable: true,
    codexRepoPath: '',
    codexPythonPath: ''
  });

  assert.equal(result.codexPathError, '');
  assert.equal(result.generatedFiles.length, 1);
  assert.equal(result.generatedFiles[0].path, '.codex/config.toml');
  assert.match(result.generatedFiles[0].content, /command = "python"/);
  assert.match(result.generatedFiles[0].content, /args = \["core\/tools\/memory_mcp.py"\]/);
});

test('buildGeneratedFiles rejects missing absolute Codex paths when portable mode is off', function () {
  const result = setupUtils.buildGeneratedFiles({
    selectedPlatform: 'codex',
    codexPortable: false,
    codexRepoPath: '',
    codexPythonPath: ''
  });

  assert.equal(result.generatedFiles.length, 0);
  assert.equal(
    result.codexPathError,
    'Enter both the absolute repo path and the absolute Python path before generating a Codex config.'
  );
});

test('buildGeneratedFiles rejects non-absolute Codex paths when portable mode is off', function () {
  const result = setupUtils.buildGeneratedFiles({
    selectedPlatform: 'codex',
    codexPortable: false,
    codexRepoPath: './repo',
    codexPythonPath: 'python'
  });

  assert.equal(result.generatedFiles.length, 0);
  assert.equal(
    result.codexPathError,
    'Codex config generation requires absolute paths for both the repo and the Python interpreter.'
  );
});

test('buildGeneratedFiles creates profile and absolute Codex files when inputs are valid', function () {
  const result = setupUtils.buildGeneratedFiles({
    selectedProfile: 'software-developer',
    profiles: {
      'software-developer': {
        body: '# User Profile\n\nProfile body'
      }
    },
    selectedPlatform: 'codex',
    userName: 'Alex',
    userCtx: 'Writing code',
    codexPortable: false,
    codexRepoPath: 'C:\\Users\\alex\\repo\\',
    codexPythonPath: 'C:\\Users\\alex\\repo\\.venv\\Scripts\\python.exe',
    now: new Date(2026, 0, 2)
  });

  assert.equal(result.codexPathError, '');
  assert.equal(result.generatedFiles.length, 3);
  assert.equal(result.generatedFiles[0].path, 'core/memory/users/profile.md');
  assert.match(result.generatedFiles[0].content, /created: 2026-01-02/);
  assert.equal(result.generatedFiles[1].path, 'core/memory/users/SUMMARY.md');
  assert.match(result.generatedFiles[1].content, /\*\*User:\*\* Alex/);
  assert.match(result.generatedFiles[1].content, /\*\*Uses AI for:\*\* Writing code/);
  assert.equal(result.generatedFiles[2].path, '.codex/config.toml');
  assert.match(result.generatedFiles[2].content, /cwd = "C:\\\\Users\\\\alex\\\\repo"/);
  assert.match(result.generatedFiles[2].content, /core\\\\tools\\\\memory_mcp.py/);
});

test('buildNextSteps returns platform-specific setup guidance', function () {
  const codexSteps = setupUtils.buildNextSteps({ generatedFileCount: 1, selectedPlatform: 'codex' });
  const genericSteps = setupUtils.buildNextSteps({ generatedFileCount: 1, selectedPlatform: 'generic' });
  const claudeSteps = setupUtils.buildNextSteps({ generatedFileCount: 0, selectedPlatform: 'claude-code' });

  assert.equal(codexSteps[0].text, 'Download the files above and place them in your Engram repo, overwriting any existing files at the same paths.');
  assert.ok(codexSteps.some(function (step) { return step.text.indexOf('Codex desktop') !== -1; }));
  assert.ok(genericSteps.some(function (step) { return step.text.indexOf('system-prompt.txt') !== -1; }));
  assert.ok(claudeSteps.some(function (step) { return step.codeSnippet === 'claude'; }));
});

test('isAbsolutePath recognizes Windows, UNC, and POSIX roots', function () {
  assert.equal(setupUtils.isAbsolutePath('C:\\repo'), true);
  assert.equal(setupUtils.isAbsolutePath('\\\\server\\share'), true);
  assert.equal(setupUtils.isAbsolutePath('/repo'), true);
  assert.equal(setupUtils.isAbsolutePath('./repo'), false);
});