# Troubleshooting & Debugging Guide

This guide covers the most common issues you'll hit when working with Engram — git problems, CI failures, pre-commit hooks, validation errors, MCP server quirks, and setup headaches. Each section is structured as **symptom → diagnosis → fix**.

If you're setting up Engram for the first time, start with [QUICKSTART.md](QUICKSTART.md) instead.

---

## Quick reference

| Symptom | Jump to |
|---------|---------|
| `pre-commit` fails on commit | [Pre-commit hooks](#pre-commit-hooks) |
| GitHub Actions CI is red | [GitHub CI failures](#github-ci-failures) |
| `ERROR: ... missing frontmatter key` | [Validation errors](#validation-error-reference) |
| ACCESS.jsonl merge conflict | [Git issues → ACCESS.jsonl conflicts](#accessjsonl-merge-conflicts) |
| Unexpected file diffs on Windows | [Git issues → Line endings](#line-endings-windows) |
| Branch confusion (`core` vs `main` vs `agent-memory`) | [Git issues → Branches](#branch-confusion) |
| MCP server won't start | [MCP server issues](#mcp-server-issues) |
| `setup.sh` fails or skips steps | [Setup issues](#setup-issues) |
| Tests fail locally | [Testing & validation](#testing--validation) |
| Need AI help debugging | [Getting help from AI](#getting-help-from-ai) |

---

## Git issues

### Branch confusion

Engram uses a non-standard branching model:

| Branch | Purpose |
|--------|---------|
| `core` | Default branch created by `setup.sh` — holds all memory content |
| `agent-memory` | Orphan branch used in **worktree mode** when Engram is embedded in another repo |
| `master` / `main` | Not used by Engram itself; may exist if you forked from a template |

**Common mistakes:**

- **Committing to the wrong branch.** Run `git branch` to confirm you're on `core` (standalone) or `agent-memory` (worktree mode) before committing.
- **Worktree branch checked out elsewhere.** Git warns about this. Remove stale worktrees with:
  ```bash
  git worktree list          # find stale entries
  git worktree remove <path> # clean up
  ```
- **Detached HEAD.** The system warns about this via `agent-bootstrap.toml` settings (`warn_on_detached_head`). Re-attach with `git checkout <branch-name>`.

### Line endings (Windows)

`.gitattributes` enforces LF line endings for all text files, even on Windows. If you see phantom diffs (every line changed, no visible difference), your editor or Git is adding CRLF.

**Fix:**

```bash
# Configure Git to handle line endings correctly
git config core.autocrlf input

# Re-normalize existing files
git add --renormalize .
git commit -m "Normalize line endings"
```

Make sure your editor is set to use LF for this repository.

### ACCESS.jsonl merge conflicts

`ACCESS.jsonl` files are append-only logs. When merging produces a conflict, **keep both sides** — the order of entries doesn't matter.

```
<<<<<<< HEAD
{"file": "knowledge/ai/llm-context.md", "date": "2026-03-20", ...}
=======
{"file": "knowledge/ai/llm-context.md", "date": "2026-03-21", ...}
>>>>>>> other-branch
```

**Fix:** Remove the conflict markers and keep all log entries. Each line is an independent record.

### GPG / commit signing

If you've enabled commit signing and it fails:

```bash
# Check your signing key
git config --global user.signingkey

# Test GPG
echo "test" | gpg --clearsign

# Disable temporarily if needed
git commit --no-gpg-sign -m "your message"
```

See `core/governance/update-guidelines.md` for which files *recommend* signed commits (protected-tier changes).

---

## GitHub CI failures

### Understanding the pipeline

Engram's CI runs two jobs on every push and PR:

| Job | Platforms | What it does |
|-----|-----------|--------------|
| **Validate & Test** | Ubuntu + Windows | Installs deps, runs pre-commit hooks, runs pytest, lints shell scripts (Linux only) |
| **Worktree E2E** | Windows only | End-to-end test of worktree initialization flow |

### Reading the logs

1. Go to the **Actions** tab on GitHub
2. Click the failing workflow run
3. Expand the failing job, then the failing step
4. The error message is usually in the last 20–30 lines of the step output

### Reproducing CI failures locally

CI runs the same commands you can run on your machine:

```bash
# Install dev dependencies (if you haven't already)
pip install -e ".[dev]"

# Run all pre-commit hooks (same as CI "Pre-commit gate" step)
python -m pre_commit run --all-files

# Run the full test suite (same as CI "Run tests" step)
python -m pytest HUMANS/tooling/tests/ core/tools/tests/ -v

# Lint shell scripts — Linux/macOS only (requires shellcheck)
shellcheck setup.sh HUMANS/setup/setup.sh HUMANS/tooling/scripts/onboard-export.sh
```

### Platform-specific gotchas

| Issue | Explanation |
|-------|-------------|
| **ShellCheck passes locally on Windows, fails in CI** | ShellCheck only runs on the Linux runner. You won't see these errors on Windows. Install ShellCheck locally or check the CI log. |
| **Worktree E2E fails but validate passes** | The worktree test only runs on Windows CI. If you're developing on Linux/macOS, you can't reproduce it locally without a Windows machine. |
| **Path separator errors on Windows** | Python's `os.path` uses `\` on Windows but `/` in POSIX. Tests should use `pathlib.Path` or `os.sep`-agnostic comparisons. |

### Common CI failure patterns

| Failing step | Likely cause | Quick fix |
|--------------|--------------|-----------|
| Pre-commit gate → `ruff-check` | Lint error (unused import, bad ordering) | `python -m ruff check --fix <path>` |
| Pre-commit gate → `ruff-format-check` | Formatting drift | `python -m ruff format <path>` |
| Pre-commit gate → `validate-memory-repo` | Frontmatter or ACCESS.jsonl issue | See [Validation error reference](#validation-error-reference) |
| Run tests | Test assertion failure | Run `python -m pytest <test_file> -v` locally to get the full traceback |
| ShellCheck | Shell syntax error | Read the ShellCheck error code (e.g., SC2086) at [shellcheck.net](https://www.shellcheck.net/) |

---

## Pre-commit hooks

### Installation

```bash
pip install -e ".[dev]"    # installs pre-commit, ruff, pytest, etc.
pre-commit install          # registers hooks in .git/hooks/
```

### Running manually

```bash
# Run all hooks on all files (same as CI)
pre-commit run --all-files

# Run a specific hook
pre-commit run ruff-check --all-files
pre-commit run ruff-format-check --all-files
pre-commit run validate-memory-repo --all-files
```

### Hook reference

| Hook | What it checks | Scope | Auto-fix |
|------|---------------|-------|----------|
| `ruff-check` | Lint errors, import ordering, unused variables | `HUMANS/tooling/scripts/`, `HUMANS/tooling/tests/`, `core/tools/` | `python -m ruff check --fix` |
| `ruff-format-check` | Code formatting (line length 100, style) | Same as above | `python -m ruff format` |
| `validate-memory-repo` | Memory structure, frontmatter, ACCESS logs, manifests | Entire repo | Manual — see [Validation errors](#validation-error-reference) |

### Ruff configuration

Ruff is configured in `pyproject.toml`:
- **Line length:** 100
- **Target Python:** 3.10
- **Rules:** `E` (errors), `F` (pyflakes), `W` (warnings), `I` (imports)
- **Ignored:** `E501` (line-too-long, handled by line-length setting)

### Skipping hooks temporarily

```bash
git commit --no-verify -m "WIP: work in progress"
```

**Warning:** CI will still run the same checks. Use `--no-verify` only for local WIP commits you plan to fix before pushing.

---

## Testing & validation

### Running tests

```bash
# Full test suite
python -m pytest HUMANS/tooling/tests/ core/tools/tests/ -v

# Single test file
python -m pytest core/tools/tests/test_graph_tools.py -v

# Single test
python -m pytest core/tools/tests/test_graph_tools.py::test_name -v
```

### Test directories

| Directory | What it covers |
|-----------|---------------|
| `core/tools/tests/` | MCP tools, graph analysis, memory write tools, package boundaries, cross-references |
| `HUMANS/tooling/tests/` | Setup flows, worktree initialization, validation scripts |

### Validation error reference

The `validate-memory-repo` hook runs `HUMANS/tooling/scripts/validate_memory_repo.py`. Here are the most common errors and how to fix them:

**Frontmatter errors** — files in `core/memory/` must have YAML frontmatter with required keys:

| Error | Fix |
|-------|-----|
| `missing required frontmatter key: source` | Add `source:` — allowed values: `user-stated`, `agent-inferred`, `agent-generated`, `external-research`, `skill-discovery`, `template`, `unknown` |
| `missing required frontmatter key: trust` | Add `trust:` — allowed values: `high`, `medium`, `low` |
| `missing required frontmatter key: origin_session` | Add `origin_session:` — format: `core/memory/activity/YYYY/MM/DD/chat-NNN` or special values: `setup`, `manual`, `unknown` |
| `missing required frontmatter key: created` | Add `created:` with an ISO timestamp (e.g., `2026-03-24`) |
| `invalid source value` | Check spelling; must be one of the allowed values above |

**ACCESS.jsonl errors:**

| Error | Fix |
|-------|-----|
| `malformed JSON` | Each line must be valid JSON. Check for trailing commas or unquoted strings. |
| `missing required field: helpfulness` | Every entry needs `file`, `date`, `task`, `helpfulness` (0.0–1.0), and `note` |
| `file references outside namespace` | The `file` field must reference a file within the same directory tree |

**Other validation errors:**

| Error | Fix |
|-------|-----|
| Bootstrap manifest errors | Check `agent-bootstrap.toml` for missing fields or invalid mode definitions |
| Compact startup budget exceeded | Reduce file sizes in critical-path documents (INIT.md, HOME.md) |
| Missing heading in scratchpad | Scratchpad files require specific headings: *Active threads*, *Immediate next actions*, *Open questions*, *Drill-down refs* |
| Missing heading in summary | Summary files require: *Live themes*, *Recent continuity*, *Retrieval guide* |

### Coverage window

The validator checks that ACCESS.jsonl logs are recent enough. The default window is 30 days. Override it with:

```bash
MEMORY_VALIDATE_COVERAGE_WINDOW_DAYS=90 pre-commit run validate-memory-repo --all-files
```

---

## MCP server issues

The MCP (Model Context Protocol) server lets AI agents interact with your memory through a tool interface. See [MCP.md](MCP.md) for the full architecture.

### Server won't start

**Check Python is available:**

```bash
python --version   # Needs 3.10+
```

**Check dependencies are installed:**

```bash
pip install -e ".[dev]"
```

**Check the entry point exists:**

```bash
# The server lives at:
python core/tools/memory_mcp.py
```

### AGENT_MEMORY_ROOT misconfiguration

The MCP server needs to know where your Engram repo lives. This is set via the `AGENT_MEMORY_ROOT` environment variable in your MCP client config.

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": ["<path-to-engram>/core/tools/memory_mcp.py"],
      "env": { "AGENT_MEMORY_ROOT": "<path-to-engram>" }
    }
  }
}
```

**Common mistakes:**
- Path contains `~` but the client doesn't expand it → use the full absolute path
- Path uses `\` on Windows but needs `/` (or escaped `\\`) in JSON
- Path points to the worktree instead of the repo root (or vice versa)

### Platform-specific config locations

| Platform | Config file location |
|----------|---------------------|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Codex | `.codex/config.toml` in the project root |
| Cursor | `.cursor/mcp.json` in the project root |

See `HUMANS/tooling/mcp-config-example.json` for a working example.

### Fallback: direct file access

If the MCP server is unavailable, agents can still interact with Engram by reading and writing files directly. This is less governed (no tool-level validation), but it works. The agent instructions in `AGENTS.md` and `core/INIT.md` describe both paths.

---

## Setup issues

### Python version

Engram requires **Python 3.10 or later**. Check with:

```bash
python --version
```

On some systems, use `python3` instead of `python`.

### Dependency installation

```bash
pip install -e ".[dev]"
```

If this fails:
- **Permission error:** Use `pip install --user -e ".[dev]"` or activate a virtual environment first
- **Missing pip:** Install with `python -m ensurepip --upgrade`
- **Conflicting versions:** Create a fresh venv: `python -m venv .venv && source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows)

### Git version

`setup.sh` uses `git init --initial-branch=core`, which requires **Git 2.28+**. Check with:

```bash
git --version
```

If your Git is older, the setup script has a compatibility fallback, but upgrading Git is recommended.

### setup.sh flags

If `setup.sh` doesn't behave as expected, check the flags you're passing:

```bash
./setup.sh --non-interactive --platform claude-code --profile software-developer
```

Available platforms: `codex`, `claude-code`, `cursor`, `chatgpt`, `generic`

Available profiles: `software-developer`, `researcher`, `project-manager`, `writer`, `student`, `educator`, `designer` (check `HUMANS/setup/templates/profiles/` for the current list)

### Worktree initialization

If `init-worktree.sh` fails:
- Make sure you're running it from within a git repository
- The orphan branch name defaults to `agent-memory` — check for name collisions
- The worktree path defaults to `.agent-memory` — make sure nothing already exists there

---

## Getting help from AI

AI agents (Claude, GPT, Copilot, etc.) can be powerful troubleshooting partners for Engram. Here's how to get the best results.

### What to include in your prompt

When asking an AI for help, provide:

1. **The exact error message** — copy-paste, don't paraphrase
2. **What you were doing** — the command you ran or action you took
3. **Your OS** — Windows, macOS, or Linux
4. **Your branch** — `git branch --show-current`
5. **Whether you're in standalone or worktree mode**

### Example prompts

> "Pre-commit is failing with `ERROR: core/memory/knowledge/ai/llm-context.md: missing required frontmatter key: trust`. How do I fix the frontmatter in this file?"

> "GitHub CI is red on the `validate` job, Windows runner. The failing step is `Run tests` and the error is `AssertionError: expected '/' separator but got '\\'`. How do I make this test cross-platform?"

> "I ran `setup.sh --platform codex --profile researcher` but no `.codex/config.toml` was created. Here's the terminal output: [paste output]"

### How AI agents interact with Engram

If the MCP server is running, AI agents access your memory through **governed tools** — these enforce validation rules, trust levels, and access logging automatically. When MCP isn't available, agents fall back to direct file reads/writes.

Key things to know:
- **Read operations are always safe.** Agents can freely read any file.
- **Write operations are governed.** Changes to `core/governance/` and `core/memory/skills/` are protected-tier and require explicit approval.
- **ACCESS.jsonl logging** is expected on every content retrieval — agents should log what they read and how helpful it was.
- **Trust levels** (`high`, `medium`, `low`) control how agents use the information they find. Low-trust content informs but doesn't instruct.

### Using AI to fix validation errors

Paste the full output of `pre-commit run --all-files` into your AI chat. The agent can:
- Diagnose which frontmatter fields are wrong and suggest corrected YAML
- Identify malformed ACCESS.jsonl entries and fix the JSON
- Explain what the validator expects and why
- Make the edits directly if it has file access

### Using AI to understand CI logs

Copy the relevant section of a GitHub Actions log and ask the AI to explain it. Focus on pasting the **error lines**, not the entire log. The agent can identify whether the issue is a lint error, test failure, validation problem, or platform incompatibility.

---

## Related documentation

> **Tip:** All docs below can also be browsed in the [documentation viewer](../views/docs.html) — a styled reader with sidebar navigation.

| Document | What it covers |
|----------|---------------|
| [QUICKSTART.md](QUICKSTART.md) | First-time setup walkthrough |
| [CORE.md](CORE.md) | Architecture rationale and design principles |
| [DESIGN.md](DESIGN.md) | Product philosophy and future directions |
| [MCP.md](MCP.md) | MCP server architecture and tool reference |
| [WORKTREE.md](WORKTREE.md) | Worktree mode, CI exemptions, tooling-bleed prevention |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Third-party tool integrations |
| [GLOSSARY.md](GLOSSARY.md) | Definitions of key terms (trust level, maturity stage, etc.) |

---

## Still stuck?

- **Check the changelog:** Recent fixes are listed in `CHANGELOG.md` at the repo root — your issue may already be resolved.
- **Open an issue:** File a bug report on GitHub with the error output, your OS, and the steps to reproduce.
- **Ask an AI:** Paste this guide's [relevant section](#quick-reference) plus your error into any AI chat for targeted help.
