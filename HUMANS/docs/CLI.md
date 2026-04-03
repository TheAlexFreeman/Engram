# Engram CLI

The `engram` CLI provides a terminal-oriented interface for searching, inspecting, and validating an Engram repository:

- `engram search` for querying memory content from a shell or script.
- `engram status` for a compact health dashboard.
- `engram add` for governed ingestion into `memory/knowledge/_unverified/`.
- `engram approval` for listing and resolving pending plan approval requests from a shell or script.
- `engram plan` for plan list/show/create/advance workflows from a shell or script.
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

### `engram add`

Adds new knowledge through a preview-first CLI flow. The command always routes writes into `memory/knowledge/_unverified/`, generates low-trust provenance frontmatter, updates the unverified summary when the matching section exists, and records a create-mode ACCESS entry on apply.

Examples:

```bash
engram add knowledge/react ./notes/hooks.md --session-id memory/activity/2026/04/03/chat-001 --preview
engram add knowledge/react ./notes/hooks.md --session-id memory/activity/2026/04/03/chat-001
cat hooks.md | engram add knowledge/react --name hooks-recap --session-id memory/activity/2026/04/03/chat-001
engram add memory/knowledge/react ./notes/hooks.md --session-id memory/activity/2026/04/03/chat-001 --json
```

`<namespace>` accepts `knowledge/...`, `memory/knowledge/...`, or an explicit path already under `memory/knowledge/_unverified/...`. Verified knowledge paths are automatically rewritten into `_unverified/` for safe ingestion. When reading from stdin, `--name` is required unless the markdown contains an H1 heading that can be converted into a filename.

JSON output mirrors the governed write result shape: `new_state` includes the created path, version token, and ACCESS log path on apply, while `preview` carries the dry-run envelope when `--preview` is used.

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

### `engram plan`

Inspects and authors structured plans from the Active Plans system without requiring an MCP host.

- `engram plan list` shows plan ids, status, progress, and next-action summaries.
- `engram plan show <plan-id>` renders the current actionable phase, including sources, blockers, postconditions, and planned changes.
- `engram plan create [file|-]` accepts YAML matching the `memory_plan_create` input contract, validates it, and creates the governed plan file. Use `--preview` to validate without writing, or `--json-schema` to print the nested authoring schema.
- `engram plan advance <plan-id>` moves the selected phase one legal step forward: it starts a pending/blocked phase, or completes an in-progress phase when `--commit-sha` is supplied. Use `--verify` to evaluate postconditions before completion and `--review-file` to attach the final review payload when the last phase closes.

Examples:

```bash
engram plan list
engram plan list --status active --json
engram plan show cli-v3-plan-commands --project cli-expansion
engram plan show cli-v3-plan-commands --project cli-expansion --phase plan-read-surfaces
engram plan create ./new-plan.yaml --preview
cat new-plan.yaml | engram plan create --json
engram plan create --json-schema
engram plan advance cli-v3-plan-commands --project cli-expansion --session-id memory/activity/2026/04/03/chat-001
engram plan advance cli-v3-plan-commands --project cli-expansion --session-id memory/activity/2026/04/03/chat-001 --commit-sha abc1234 --verify
engram plan advance cli-v3-plan-commands --project cli-expansion --session-id memory/activity/2026/04/03/chat-001 --commit-sha abc1234 --review-file ./review.yaml
```

`engram plan create --help` renders schema-backed authoring guidance generated from the same nested contract used by `memory_plan_schema` and `engram-mcp plan create --json-schema`.

When `engram plan advance` hits unresolved blockers or an approval-gated phase, it surfaces the blocked or paused state instead of guessing a bypass. Approval resolution still uses the MCP-hosted approval tools until the terminal approval commands land.

For local terminal work, `engram plan list`, `engram plan show`, `engram plan create`, and `engram plan advance` can replace the direct MCP read/create/execute surfaces for day-to-day plan authoring and progression. Use the MCP-hosted plan and approval tools when you need approval resolution, run-state coordination beyond the simple advance flow, or other review/observability commands that do not yet have terminal equivalents.

JSON output mirrors the underlying plan runtime: `list` returns structured plan summaries with `next_action` and `phase_progress`, `show` returns the selected phase packet plus plan progress and optional budget status, `create` returns the governed write result or preview envelope, and `advance` returns the shared execute payload for started/completed/blocked/paused/verification states.

### `engram approval`

Inspects and resolves structured-plan approval requests from the terminal.

- `engram approval list` shows pending approvals with stable ids, scope, expiry metadata, and the stored phase context needed to decide whether the work should proceed. Pending approvals that have aged past `expires` are surfaced as `expired` without mutating the repository.
- `engram approval resolve <approval-id> approve|reject` records the reviewer decision, moves the approval file into the resolved queue, and updates the plan status to `active` or `blocked`. Use `--preview` to render the governed write envelope before mutating the repository.

Examples:

```bash
engram approval list
engram approval list --json
engram approval resolve tracked-plan--phase-a approve --comment "Looks good."
engram approval resolve tracked-plan--phase-a reject --comment "Need more detail." --json
engram approval resolve tracked-plan--phase-a approve --preview
```

Malformed approval ids fail fast, and expired approvals are rejected with a clear diagnostic instead of being silently rewritten.

JSON output includes approval ids, scope, status, expiry metadata, the stored approval context for `list`, and the governed write result for `resolve`.

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
- `engram add --json` emits a governed write result with `preview` support for dry runs.
- `engram plan list --json` emits structured plan summaries for scripts or terminal agents.
- `engram plan show --json` emits the selected phase packet with blockers, postconditions, and changes.
- `engram plan create --json` emits the governed create result or preview envelope for terminal plan authoring.
- `engram plan create --json-schema` emits the raw nested plan-authoring schema mirrored from `memory_plan_schema`.
- `engram plan advance --json` emits the shared plan-execute payload, including blocked, paused, verification, and successful transition states.
- `engram approval list --json` emits approval ids, scope, status, expiry metadata, and stored phase context.
- `engram approval resolve --json` emits the governed approval-resolution write result, including the resolved approval id, plan status, and commit metadata.
- `engram recall --json` emits a structured file or namespace inspection payload.
- `engram log --json` emits a filtered ACCESS timeline payload.

For onboarding and broader setup instructions, see [QUICKSTART.md](QUICKSTART.md).
