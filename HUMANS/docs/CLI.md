# Engram CLI

The `engram` CLI provides a terminal-oriented interface for searching, inspecting, and validating an Engram repository:

- `engram search` for querying memory content from a shell or script.
- `engram status` for a compact health dashboard.
- `engram recall` for reading a file or namespace with frontmatter and ACCESS context.
- `engram log` for recent ACCESS timeline inspection.
- `engram validate` for repository integrity checks.

## Installation

For the full CLI surface, install the core optional dependencies:

```bash
python -m pip install -e ".[core]"
```

If you want semantic search instead of keyword-only fallback, install the search extras too:

```bash
python -m pip install -e ".[core,search]"
```

## Repo Root Resolution

`engram` resolves the target repository in this order:

1. `--repo-root <path>`
2. `MEMORY_REPO_ROOT`
3. `AGENT_MEMORY_ROOT`
4. Walking upward from the current working directory until it finds an Engram repo
5. Falling back to the repository that contains the installed CLI module

Every subcommand also supports `--json` for script-friendly output.

## Command Reference

### `engram status`

Shows the current maturity stage, last periodic review date, ACCESS pressure, pending review-queue items, overdue unverified content, and active plans.

Examples:

```bash
engram status
engram status --json
engram status --repo-root ~/memory
```

### `engram search`

Searches markdown memory content. By default it uses semantic search when `sentence-transformers` is installed; otherwise it falls back to keyword search automatically. Use `--keyword` to force keyword mode.

Examples:

```bash
engram search "periodic review"
engram search "session health" --keyword
engram search "validation" --scope memory/skills --limit 5
engram search "context budget" --json
```

JSON output includes the selected mode plus a structured list of results with path, trust, snippet, and score when semantic search is active.

### `engram recall`

Reads a memory file with its frontmatter and ACCESS context, or inspects a namespace by showing its `SUMMARY.md` plus a file listing. If the target does not resolve to a path, `recall` falls back to search and loads the best match.

Examples:

```bash
engram recall memory/knowledge/software-engineering/parser.md
engram recall knowledge/software-engineering
engram recall "task similarity method" --keyword
engram recall memory/knowledge/software-engineering/parser.md --json
```

JSON output includes the resolved kind (`file` or `namespace`), the selected path, frontmatter, ACCESS summary, and either file content or namespace entries.

### `engram log`

Shows recent `ACCESS.jsonl` entries in a human-readable timeline. Use namespace aliases such as `knowledge`, `skills`, `identity`, or `plans`, and optionally limit by date.

Examples:

```bash
engram log
engram log --namespace knowledge --limit 10
engram log --namespace plans --since 2026-04-01
engram log --namespace knowledge --since 2026-04-01 --json
```

JSON output includes the filtered result count plus structured ACCESS entries with namespace labels.

### `engram validate`

Runs the repository validator and exits with stable status codes:

- `0` clean
- `1` warnings only
- `2` errors present

Examples:

```bash
engram validate
engram validate --json
```

If the validator's core dependencies are missing, the command prints a friendly install hint instead of a Python traceback.

## Scripting Notes

- `engram validate --json` emits a JSON array of findings.
- `engram status --json` emits a structured object suitable for dashboards or shell pipelines.
- `engram search --json` emits a structured object with the search mode and result list.
- `engram recall --json` emits a structured file or namespace inspection payload.
- `engram log --json` emits a filtered ACCESS timeline payload.

For onboarding and broader setup instructions, see [QUICKSTART.md](QUICKSTART.md).
