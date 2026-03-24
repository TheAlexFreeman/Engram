(function (root) {
  'use strict';

  function today(now) {
    now = now || new Date();
    var year = String(now.getFullYear());
    var month = String(now.getMonth() + 1).padStart(2, '0');
    var day = String(now.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  function makeFrontmatter(source, trust, now) {
    var date = today(now);
    return '---\nsource: ' + source + '\norigin_session: setup\ncreated: ' + date +
      '\ntrust: ' + trust + '\n---\n\n';
  }

  function escapeTomlString(value) {
    return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function makeCodexConfigPortable() {
    return [
      '# Codex MCP config for agent-memory. Portable across systems when run from repo root.',
      '# Uses relative paths and python; run setup.sh without --codex-portable to generate',
      '# machine-specific paths if Codex App requires absolute paths (see openai/codex#14573).',
      '[mcp_servers.agent_memory]',
      'command = "python"',
      'args = ["core/tools/memory_mcp.py"]',
      'cwd = "."',
      'startup_timeout_sec = 20',
      'tool_timeout_sec = 120',
      'required = false',
      'env_vars = ["MEMORY_REPO_ROOT", "AGENT_MEMORY_ROOT"]'
    ].join('\n');
  }

  function makeCodexConfig(repoPath, pythonPath) {
    var normalizedRepo = repoPath.trim();
    var normalizedPython = pythonPath.trim();
    var sep = (normalizedRepo.indexOf('\\') !== -1 || /^[A-Za-z]:/.test(normalizedRepo)) ? '\\' : '/';
    var trimmedRepo = normalizedRepo.replace(/[\\/]+$/, '');
    var memoryScript = trimmedRepo + sep + 'core' + sep + 'tools' + sep + 'memory_mcp.py';
    return [
      '[mcp_servers.agent_memory]',
      'command = "' + escapeTomlString(normalizedPython) + '"',
      'args = ["' + escapeTomlString(memoryScript) + '"]',
      'cwd = "' + escapeTomlString(trimmedRepo) + '"',
      'startup_timeout_sec = 20',
      'tool_timeout_sec = 120',
      'required = false',
      '',
      '[mcp_servers.agent_memory.env]',
      'MEMORY_REPO_ROOT = "' + escapeTomlString(trimmedRepo) + '"'
    ].join('\n');
  }

  function isAbsolutePath(value) {
    return /^[A-Za-z]:[\\/]/.test(value) || /^\\\\[^\\]+\\[^\\]+/.test(value) || value.startsWith('/');
  }

  function buildGeneratedFiles(opts) {
    opts = opts || {};

    var generatedFiles = [];
    var codexPathError = '';
    var selectedProfile = opts.selectedProfile;
    var profiles = opts.profiles || {};
    var selectedPlatform = opts.selectedPlatform;
    var userName = (opts.userName || '').trim();
    var userCtx = (opts.userCtx || '').trim();
    var codexPortable = opts.codexPortable !== false;
    var codexRepoPath = (opts.codexRepoPath || '').trim();
    var codexPythonPath = (opts.codexPythonPath || '').trim();

    if (selectedProfile && profiles[selectedProfile]) {
      generatedFiles.push({
        path: 'core/memory/users/profile.md',
        content: makeFrontmatter('template', 'medium', opts.now) + profiles[selectedProfile].body
      });

      var summaryLines = [
        '# Identity Summary',
        '',
        'Template-based profile - pending onboarding confirmation.',
        '',
        'A starter profile has been installed from a template. During the first',
        'session, the onboarding skill will walk through the template traits and',
        'confirm, adjust, or remove them.',
        '',
        'See [profile.md](profile.md) for the current profile.'
      ];

      if (userName) {
        summaryLines.push('', '**User:** ' + userName);
      }
      if (userCtx) {
        summaryLines.push('**Uses AI for:** ' + userCtx);
      }

      generatedFiles.push({
        path: 'core/memory/users/SUMMARY.md',
        content: summaryLines.join('\n')
      });
    }

    if (selectedPlatform === 'codex') {
      if (codexPortable) {
        generatedFiles.push({
          path: '.codex/config.toml',
          content: makeCodexConfigPortable()
        });
      } else if (!codexRepoPath || !codexPythonPath) {
        codexPathError = 'Enter both the absolute repo path and the absolute Python path before generating a Codex config.';
      } else if (!isAbsolutePath(codexRepoPath) || !isAbsolutePath(codexPythonPath)) {
        codexPathError = 'Codex config generation requires absolute paths for both the repo and the Python interpreter.';
      } else {
        generatedFiles.push({
          path: '.codex/config.toml',
          content: makeCodexConfig(codexRepoPath, codexPythonPath)
        });
      }
    } else if (selectedPlatform === 'chatgpt') {
      generatedFiles.push({ path: 'chatgpt-instructions.txt', content: opts.chatgptInstructions || '' });
    } else if (selectedPlatform === 'generic') {
      generatedFiles.push({ path: 'system-prompt.txt', content: opts.genericSystemPrompt || '' });
    }

    return {
      codexPathError: codexPathError,
      generatedFiles: generatedFiles
    };
  }

  function buildNextSteps(opts) {
    opts = opts || {};
    var steps = [];

    function addStep(text, codeSnippet) {
      steps.push({ text: text, codeSnippet: codeSnippet || '' });
    }

    if ((opts.generatedFileCount || 0) > 0) {
      addStep('Download the files above and place them in your Engram repo, overwriting any existing files at the same paths.');
    }
    addStep('If you want to sync this repo to GitHub, GitLab, or another remote, configure that manually outside this wizard.');
    addStep('Review the local changes with `git status --short` and commit them intentionally once the files are in place.');

    if (opts.selectedPlatform === 'codex') {
      addStep('Open the repo in Codex desktop and trust the project so `.codex/config.toml` is applied.');
      addStep('Restart or reopen the repo if Codex was already running.');
    } else if (opts.selectedPlatform === 'claude-code') {
      addStep('Start your first session:', 'claude');
    } else if (opts.selectedPlatform === 'cursor') {
      addStep('Open the repo folder in Cursor and start a conversation.');
    } else if (opts.selectedPlatform === 'chatgpt') {
      addStep('Paste the contents of chatgpt-instructions.txt into ChatGPT -> Settings -> Personalization -> Custom Instructions.');
      addStep('Start a conversation and share `core/INIT.md` plus whatever files it routes the agent to load.');
    } else if (opts.selectedPlatform === 'generic') {
      addStep('Copy the contents of system-prompt.txt into your AI platform\'s system prompt.');
      addStep('Start a conversation and share `core/INIT.md` plus whatever files it routes the agent to load.');
    } else {
      addStep('See HUMANS/docs/QUICKSTART.md for platform-specific instructions.');
    }

    addStep('The agent will run the onboarding skill and ask you a few questions to build your profile.');
    return steps;
  }

  var api = {
    today: today,
    makeFrontmatter: makeFrontmatter,
    escapeTomlString: escapeTomlString,
    makeCodexConfigPortable: makeCodexConfigPortable,
    makeCodexConfig: makeCodexConfig,
    isAbsolutePath: isAbsolutePath,
    buildGeneratedFiles: buildGeneratedFiles,
    buildNextSteps: buildNextSteps
  };

  root.EngramSetup = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
}(typeof window !== 'undefined' ? window : globalThis));