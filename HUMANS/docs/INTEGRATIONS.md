# Integrating Engram

This guide covers the supported integration modes for this repository, with extra focus on **worktree mode**: deploying the memory store as an orphan-branch worktree inside an existing host repository.

Use this document when you need to:

- attach the memory system to an existing codebase
- keep the memory branch out of host CI, release automation, and PR workflows
- prevent host formatters, linters, and search tools from treating the memory worktree as application code
- wire an MCP-capable client to either the standalone repo or a deployed worktree

## Integration modes

### Standalone repo

Use the repository as-is when the memory system is the primary project.

- run `setup.sh` from the repo root
- keep agent adapter files in the repo root
- point your MCP client at `core/tools/memory_mcp.py` or `engram-mcp`

### Worktree mode

Use `setup/init-worktree.sh` when you want a host codebase to keep its own persistent memory without mixing memory commits into product history.

- host repository: application code, normal branch protection, normal CI
- memory branch: orphan branch such as `agent-memory`
- memory worktree: directory such as `.agent-memory/`
- agent adapters: written to the host root so sessions start in the right place
- memory operations: target the worktree
- host git operations: target the host repo via `host_repo_root`

### Embedded MCP

If you already have an agent runtime, prefer MCP over direct file access whenever possible.

- server entrypoint: `core/tools/memory_mcp.py`
- installed CLI: `engram-mcp`
- repo root env var: `MEMORY_REPO_ROOT`
- optional host repo env var in worktree mode: `HOST_REPO_ROOT`

## Worktree mode quick start

Run the init script from the **host repository root**:

```bash
bash setup/init-worktree.sh \
    --non-interactive \
    --platform codex \
    --profile software-developer \
    --worktree-path .agent-memory \
    --branch-name agent-memory
```

The script will:

1. create an orphan memory branch
2. materialize the memory worktree at the configured path
3. write host-root adapter files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`)
4. write MCP client config for the selected platform
5. seed a starter codebase-survey plan and `core/memory/knowledge/codebase/` skeleton
6. add worktree-local `.ignore` and `.editorconfig` defaults

## Worktree mode: CI/CD exemptions

Treat the memory branch as **operational state**, not as a deployable application branch. It should usually be exempt from normal CI gates, branch protection, and release-note tooling.

### GitHub Actions

Ignore the memory branch on `push` and `pull_request` triggers.

```yaml
on:
    push:
        branches-ignore:
            - agent-memory
    pull_request:
        branches-ignore:
            - agent-memory
```

If you use a custom memory branch name, replace `agent-memory` everywhere with that configured value.

### GitHub branch protection

Do not apply your mainline protection rules to the memory branch.

- exclude it from required status checks
- exclude it from required reviews
- exclude it from merge queues and deployment environments
- avoid using it as a source or target in normal pull requests

If your organization applies wildcard branch rules, add a more specific exemption for the memory branch.

### GitHub PR and release-note noise

Keep the memory branch out of normal review and release workflows.

- do not open PRs from the memory branch into product branches except for deliberate debugging
- exclude the memory branch from any branch enumeration your release tooling performs
- if you use generated release notes, ensure the job only considers your shipping branches or tagged merges

### GitLab CI

Use workflow rules or per-job rules to skip the memory branch entirely.

```yaml
workflow:
    rules:
        - if: '$CI_COMMIT_BRANCH == "agent-memory"'
            when: never
        - when: always
```

For existing per-job pipelines, use the same branch check in `rules:` blocks.

### Bitbucket Pipelines

Bitbucket does not have a direct `branches-ignore` equivalent for every pipeline layout, so use a branch gate near the top of the pipeline or split your branch selectors explicitly.

```yaml
pipelines:
    default:
        - step:
                name: Host CI
                script:
                    - if [ "$BITBUCKET_BRANCH" = "agent-memory" ]; then echo "Skipping memory branch"; exit 0; fi
                    - ./ci.sh
```

If you already use `branches:` selectors, omit the memory branch there and keep it out of `default` when practical.

## Worktree mode: tooling-bleed prevention

The memory worktree should not be treated like host application code by default. Exclude the worktree path from formatters, linters, type checkers, and editor search where possible.

Assume the deployed worktree path is `.agent-memory/`. Replace that path if you configured a different location.

### Built-in worktree defaults

`init-worktree.sh` now writes two worktree-local files automatically:

- `.ignore` to keep memory-content folders out of host-repo searches by default
- `.editorconfig` to stop host-root formatting rules from leaking into the memory files

If you intentionally search inside the memory worktree, use `rg --no-ignore`, `fd --no-ignore`, or the equivalent editor setting.

### ESLint

Add the worktree path to `.eslintignore`:

```text
.agent-memory/
```

### Prettier

Add the worktree path to `.prettierignore`:

```text
.agent-memory/
```

### Ruff and Black

Exclude the worktree path in `pyproject.toml` so Python tooling does not recurse into the memory files.

```toml
[tool.ruff]
exclude = [".agent-memory"]

[tool.black]
extend-exclude = "(^|/).agent-memory/"
```

If you already maintain larger exclude lists, append the worktree path instead of replacing the existing values.

### TypeScript

Exclude the worktree path in `tsconfig.json`:

```json
{
    "exclude": [".agent-memory"]
}
```

If `exclude` already exists, append the path.

### VS Code search

Exclude the worktree path in workspace settings:

```json
{
    "search.exclude": {
        ".agent-memory": true
    },
    "files.watcherExclude": {
        ".agent-memory/**": true
    }
}
```

### JetBrains IDEs

Mark the deployed worktree directory as **Excluded** in the Project tool window, or add it to a custom search scope exclusion if you still want it visible in the tree.

### ripgrep and fd

The generated worktree-local `.ignore` already hides the main memory folders when you search from the host repo. If you want a host-root override as well, add the worktree path to `.rgignore` or `.ignore` in the host repo root:

```text
.agent-memory/
```

### Optional host `.gitignore`

If you do not want the worktree path to appear as an untracked directory in the host repo, add it to the host root `.gitignore`:

```text
.agent-memory/
```

That does **not** affect the memory branch itself; it only keeps the host checkout clean.

## MCP client wiring

### Codex

In worktree mode, the init script writes `.codex/config.toml` in the host root. Trust that file so Codex can launch the memory MCP server from the worktree.

### Other MCP-capable clients

In worktree mode, the init script writes `mcp-config-example.json` in the host root. Copy that entry into the client-specific MCP config and preserve these fields:

- command: `engram-mcp` when installed, otherwise the Python-plus-script fallback
- cwd: the memory worktree path
- `MEMORY_REPO_ROOT`: the memory worktree path
- `HOST_REPO_ROOT`: the host repo root

## Operational guidance

- use the host repo for product-code commands, builds, and git inspection
- use the memory worktree for identity, knowledge, plans, chats, scratchpad, and governance files
- keep only one active governed writer per memory worktree
- treat generated templates as starting points; replace low-trust survey stubs with verified notes as soon as the codebase survey begins

## Minimal checklist

1. Initialize the worktree from the host repo root.
2. Exempt the memory branch from CI and branch protection.
3. Exclude the worktree path from host tooling.
4. Trust the generated MCP config for your client.
5. Start with `core/memory/working/projects/codebase-survey/plans/survey-plan.yaml` and fill `core/memory/knowledge/codebase/` as you learn the host repo.
