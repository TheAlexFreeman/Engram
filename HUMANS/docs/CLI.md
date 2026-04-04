# Engram CLI

The `engram` CLI provides a terminal-oriented interface for searching, inspecting, and validating an Engram repository:

- `engram init` for bootstrapping an Engram memory worktree inside an existing host repository.
- `engram search` for querying memory content from a shell or script.
- `engram status` for a compact health dashboard.
- `engram add` for governed ingestion into `memory/knowledge/_unverified/`.
- `engram review` for shell-first maintenance candidate walkthroughs.
- `engram aggregate` for dry-run ACCESS aggregation previews.
- `engram promote` for moving reviewed `_unverified` notes into verified knowledge.
- `engram archive` for routing stale knowledge into `memory/knowledge/_archive/`.
- `engram export` for portability bundles in markdown, JSON, or tar form.
- `engram import` for previewing or applying portability bundles back into an Engram repo.
- `engram approval` for listing and resolving pending plan approval requests from a shell or script.
- `engram plan` for plan list/show/create/advance workflows from a shell or script.
- `engram trace` for querying session traces from a shell or script.
- `engram recall` for reading a file or namespace with frontmatter and ACCESS context.
- `engram log` for recent ACCESS timeline inspection.
- `engram diff` for git-backed memory history with memory-aware annotations.
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

### `engram init`

Initializes an Engram memory worktree inside the current host git repository. Creates an orphan branch, seeds the memory directory structure, installs a starter profile, writes MCP config and host adapter files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`), and scaffolds a codebase-survey project.

Run from the host repository root. Does not require an existing Engram checkout — it uses the seed content bundled with the installed package.

**Defaults:**

| Option | Default |
|---|---|
| `--platform` | `cursor` |
| `--profile` | `software-developer` |
| `--worktree-path` | `.engram` |
| `--branch-name` | `worktree--<host-repo-name>` |

Examples:

```bash
# Quick start with defaults (cursor, software-developer, .engram)
engram init

# Specify platform and profile
engram init --platform codex --profile researcher

# Custom worktree path and branch name
engram init --worktree-path .agent-memory --branch-name agent-memory

# Preview without executing
engram init --dry-run

# Include optional user context
engram init --user-name "Alice" --user-context "Full-stack web development"
```

Options:

- `--platform <name>` — AI platform for MCP config: `codex`, `claude-code`, `cursor`, `chatgpt`, `generic`.
- `--profile <name>` — Starter profile template: `software-developer`, `researcher`, `project-manager`, `designer`, `educator`, `student`, `writer`.
- `--worktree-path <path>` — Worktree path relative to the host repo root.
- `--branch-name <name>` — Orphan branch name for the memory store.
- `--user-name <name>` — Optional name for template-backed starter summaries.
- `--user-context <text>` — Optional AI-use context for template-backed starter summaries.
- `--dry-run` — Print planned git commands without executing them.

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

### `engram diff`

Inspects recent git history for memory content and annotates file changes with memory-aware context such as frontmatter edits, trust transitions, and newly added files. By default it scans the memory tree; use namespace aliases like `knowledge`, `skills`, or `plans` to narrow the history.

Examples:

```bash
engram diff
engram diff --namespace knowledge --since 2026-04-01
engram diff --namespace plans --until 2026-04-03 --json
```

JSON output includes the matched commits, changed files, namespace-level change counts, and annotations for frontmatter and trust changes.

### `engram review`

Enumerates maintenance candidates from the terminal without mutating the repository. The command groups pending review-queue items, overdue low-trust `_unverified` files, and ACCESS logs that are above or near the aggregation trigger. Use `--decision` to capture non-mutating approve, reject, or defer choices in a shell-friendly way.

The review surface is still preview-only: it helps you identify what should happen next, then hand off the actual file mutation to `engram promote` or `engram archive`.

Examples:

```bash
engram review
engram review --decision 1=approve --decision 2=defer
engram review --json
```

JSON output includes a stable candidate list with ids, candidate types, priorities, summaries, and any scripted decision previews.

### `engram aggregate`

Previews ACCESS aggregation without mutating the repository. The current CLI slice is preview-only: it reports trigger status, matching access logs, expected summary targets, archive targets, and co-retrieval clusters, but it does not yet apply the archive/reset write path.

Examples:

```bash
engram aggregate
engram aggregate --namespace knowledge
engram aggregate --namespace plans --json
```

JSON output mirrors the dry-run aggregation state: threshold reports, entries processed, summary targets, archive targets, and detected clusters.

### `engram promote`

Promotes a reviewed file from `memory/knowledge/_unverified/` into verified `memory/knowledge/`. The command reuses the governed `memory_promote_knowledge` semantics: it updates trust and `last_verified`, moves the file into the verified namespace, and updates the unverified and verified summaries when those sections exist.

Examples:

```bash
engram promote memory/knowledge/_unverified/react/hooks.md --preview
engram promote memory/knowledge/_unverified/react/hooks.md --trust medium
engram promote memory/knowledge/_unverified/react/hooks.md --target-path memory/knowledge/frontend/hooks.md --summary-entry "- **[hooks.md](memory/knowledge/frontend/hooks.md)** — Hooks"
engram promote memory/knowledge/_unverified/react/hooks.md --json
```

JSON output mirrors the governed write result: `new_state` includes the verified destination path and trust level, while `preview` exposes the dry-run envelope when `--preview` is used.

### `engram archive`

Archives a knowledge file into `memory/knowledge/_archive/`. The command reuses the governed `memory_archive_knowledge` contract: it marks the file as archived, refreshes `last_verified`, moves it out of the active retrieval tree, and removes the source summary entry when present.

Examples:

```bash
engram archive memory/knowledge/react/legacy-hooks.md --preview
engram archive memory/knowledge/react/legacy-hooks.md --reason stale
engram archive memory/knowledge/_unverified/react/superseded-note.md --reason duplicate --json
```

JSON output mirrors the governed write result: `new_state.archive_path` reports the archived destination and `preview` carries the dry-run envelope when requested.

### `engram export`

Creates a portability bundle rooted at the stable instance-specific state: `core/INIT.md`, `core/governance/review-queue.md`, and everything under `core/memory/`. Export supports three formats:

- `md` for a human-readable, round-trippable Markdown bundle.
- `json` for a machine-friendly bundle with inline file content.
- `tar` for an archive containing `manifest.json` plus the exported files at their original repo-relative paths.

Examples:

```bash
engram export --format md
engram export --format json --output ./memory-bundle.json --json
engram export --format tar --output ./memory-bundle.tar
```

When `--output` is omitted, `md` and `json` bundle content is written directly to stdout. Tar bundles require `--output`.

### `engram import`

Validates or applies a portability bundle created by `engram export`. Preview is the default mode: the command checks bundle kind, version, UTF-8 content, and file digests before showing which files would be created or overwritten. Use `--apply` to write the validated bundle into the current repo, and `--overwrite` to allow updates when existing files differ.

Examples:

```bash
engram import ./memory-bundle.json
engram import ./memory-bundle.md --json
engram import ./memory-bundle.tar --apply
engram import ./memory-bundle.json --apply --overwrite
```

`engram import` accepts only bundles produced by `engram export`; the older onboarding-export template remains a separate import path through `HUMANS/tooling/scripts/onboard-export.sh`.

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

When `engram plan advance` hits unresolved blockers or an approval-gated phase, it surfaces the blocked or paused state instead of guessing a bypass. Follow that pause with `engram approval list` and `engram approval resolve` from the terminal, or switch to the browser approval view when you need queue-oriented review across many pending items.

For local terminal work, `engram plan list`, `engram plan show`, `engram plan create`, `engram plan advance`, and `engram approval resolve` can replace the direct MCP read/create/execute surfaces for day-to-day plan authoring and progression. Use the browser views or MCP-hosted tools when you need broader queue management, richer observability, or other coordination surfaces that are still more ergonomic outside the shell.

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

Use the terminal approval commands when you already know the plan or approval id and want a direct decision path. The browser approval view remains the better fit for scanning many pending requests, comparing context across items, or triaging the queue visually.

JSON output includes approval ids, scope, status, expiry metadata, the stored approval context for `list`, and the governed write result for `resolve`.

### `engram trace`

Queries `TRACES.jsonl` spans from the terminal.

- `engram trace` reads session trace files newest-first and returns the same structured payload as `memory_query_traces`, with aggregates for total duration, total cost, status counts, and error rate.
- Filter with `--session-id`, `--date-from`, `--date-to`, `--plan`, `--span-type`, `--status`, and `--limit`.
- When `--session-id` is supplied, it narrows directly to that session trace file and does not fall back to date-range discovery.

Examples:

```bash
engram trace
engram trace --plan cli-v3-approval-trace --json
engram trace --date-from 2026-04-01 --date-to 2026-04-03 --span-type plan_action
engram trace --session-id memory/activity/2026/04/03/chat-001 --status error
```

Malformed dates, invalid session ids, and invalid plan ids fail with clear diagnostics instead of returning partial results.

`engram trace` is the fastest shell path for targeted debugging when you already know the plan, session, or date window. The browser trace view remains the better fit for exploratory browsing across sessions and for timeline-oriented inspection.

JSON output mirrors `memory_query_traces`: `spans`, `total_matched`, and `aggregates` with duration, cost, type/status counts, and error rate.

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
- `engram trace --json` emits the structured trace-query payload with spans, match counts, and aggregate duration/cost/error metrics.
- `engram recall --json` emits a structured file or namespace inspection payload.
- `engram log --json` emits a filtered ACCESS timeline payload.
- `engram diff --json` emits recent memory-history commits, changed files, namespace summaries, and memory-aware annotations.
- `engram review --json` emits maintenance candidates and scripted decision previews.
- `engram aggregate --json` emits the dry-run aggregation preview contract, including threshold reports and target files.
- `engram promote --json` emits the governed promotion result or preview envelope.
- `engram archive --json` emits the governed archive result or preview envelope.
- `engram export --json` emits export operation metadata when `--output` is used; otherwise the bundle format itself determines stdout content.
- `engram import --json` emits either the preview payload or the applied write result for the validated bundle.

For onboarding and broader setup instructions, see [QUICKSTART.md](QUICKSTART.md).
