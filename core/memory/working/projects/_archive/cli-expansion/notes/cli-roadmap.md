---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: design-note
---

# Engram CLI Roadmap

## Vision

A single `engram` command that makes the memory system feel alive outside of a chat session. Humans use it for debugging, maintenance, and quick lookups. Shell-based agents (Claude Code, Codex, etc.) use it when the MCP server isn't wired up. Automation scripts use it for CI gates and scheduled maintenance.

The CLI is a **thin presentation layer** — it does not reimplement business logic. Every command calls into the same functions that power the MCP tools.

---

## v0 — Foundation (plan: cli-v0)

The initial release ships three commands chosen for maximum leverage with minimum risk:

### `engram search <query>`
**Audience:** Everyone (the daily-driver command).

Searches across all memory namespaces. Two modes: keyword (grep-based, zero extra deps) and semantic (embedding-based, requires `.[search]` extra). Auto-detects which is available and prints a mode banner. Each result shows relative path, trust level, snippet, and similarity score (semantic only).

Key flags: `--scope` (limit to a namespace like `knowledge` or `skills`), `--limit` (cap results), `--semantic`/`--keyword` (force mode), `--json`.

**Why first:** This is the command people will reach for daily. It proves the data model works for ad-hoc queries and makes the memory system useful outside chat.

### `engram status`
**Audience:** Humans doing maintenance, agents doing self-checks.

A terminal dashboard showing memory health at a glance: maturity stage, last periodic review date, ACCESS.jsonl entry counts per namespace (with aggregation warnings), pending review-queue items, expired or near-expiry unverified content, and active plans.

Key flags: `--json`, `--verbose` (show per-file detail).

**Why first:** Right now checking memory health requires reading INIT.md + review-queue.md + counting JSONL lines manually. One command lowers the maintenance barrier, which is critical as more users adopt the system.

### `engram validate`
**Audience:** CI pipelines, pre-commit hooks, new users checking their setup.

Runs the full memory repo validator (frontmatter schema, orphaned files, broken links, SUMMARY drift, ACCESS format). Exit code 0/1/2 for clean/warnings/errors.

Key flags: `--json`, `--fix` (auto-fix simple issues like missing frontmatter fields — future).

**Why first:** The logic already exists in `validate_memory_repo.py`. Wrapping it in a discoverable command is low effort, high payoff.

---

## v1 — Read and Write

### `engram recall <path-or-query>`
Read a memory file with its frontmatter rendered as context: trust level, source, age, last verified date, access count. More useful than `cat` because it contextualizes the content. Accepts a namespace like `engram recall knowledge/react` to show the SUMMARY plus file listing.

### `engram add <namespace> [file-or-stdin]`
Governed write that respects the same rules as MCP Tier 1. External content goes to `_unverified/`, frontmatter is auto-generated with proper provenance (`source: external-research`, `trust: low`). ACCESS log is updated. Accepts Markdown from a file argument or stdin for pipe-friendly workflows.

### `engram log [--namespace] [--since]`
Show recent ACCESS.jsonl entries in a human-readable timeline. Useful for understanding what an agent retrieved and why. Filters by namespace and date range.

---

## v2 — Maintenance and Governance

### `engram review`
Interactive walkthrough of the review queue, stale content, and aggregation candidates. For each item, the user can approve, reject, or defer. Supports a `--no-tui` mode that prints items as a numbered list and accepts responses inline (for terminals without TUI support or for scripted responses).

### `engram aggregate [--namespace] [--dry-run]`
Run the ACCESS.jsonl aggregation cycle manually. Refreshes SUMMARY.md files, identifies high-value and low-value files, archives processed entries. `--dry-run` shows what would change without writing.

### `engram promote <path>`
Move a file from `_unverified/` to its target namespace after human review. Updates frontmatter (trust: low → medium, adds `last_verified`), logs the promotion in ACCESS.

### `engram archive <path>`
Move a file to `_archive/` with proper metadata updates and ACCESS logging.

---

## v3 — Plans and Agent Coordination

### `engram plan list|show|create|advance`
Expose the Active Plans system for agents in automation contexts. `list` shows active plans with status. `show <plan-id>` renders the current phase with its sources, postconditions, and changes. `create` accepts YAML from stdin or a file. `advance` marks the current phase complete and shows the next one.

### `engram approval list|resolve`
Surface pending HITL approval requests. `list` shows pending items. `resolve <id> --approve|--reject` records the decision. Enables approval workflows from the terminal without needing the browser UI.

### `engram trace [--plan] [--session] [--since]`
Query the trace/observability system. Show execution traces for plans, sessions, or date ranges. Useful for post-hoc debugging of what an agent did and why.

---

## v4 — Export and Multi-Instance

### `engram export [--format md|json|tar]`
Dump a portable snapshot for migration, backup, or seeding a new instance. The Markdown format produces a single document. JSON produces a structured bundle. Tar produces a minimal archive of core/memory/ with frontmatter intact.

### `engram import <source>`
Seed a new Engram instance from an export bundle. Useful for team onboarding — a senior team member exports their knowledge base, a new member imports the shared subset.

### `engram diff [--since <date>] [--namespace]`
Show what changed in memory since a date, formatted for human review. Wraps git log with memory-aware annotations (frontmatter changes, trust level changes, new files by namespace).

---

## Architecture Notes

### Module layout
```
core/tools/agent_memory_mcp/cli/
├── __init__.py
├── main.py           # Entry point, parser, repo root resolution
├── cmd_search.py     # engram search
├── cmd_status.py     # engram status
├── cmd_validate.py   # engram validate
├── cmd_recall.py     # (v1) engram recall
├── cmd_add.py        # (v1) engram add
├── validators.py     # Importable validation core (shared with pre-commit)
└── formatting.py     # Shared output formatting (tables, JSON, colors)
```

### Design principles
1. **Reuse, don't reimplement.** Every command calls into existing `engram_mcp` functions.
2. **`--json` everywhere.** Structured output on every command for agent/script consumption.
3. **Graceful degradation.** Missing optional deps (sentence-transformers, etc.) produce helpful messages, not crashes.
4. **Repo root auto-discovery.** Same resolution chain as the MCP server, plus cwd-walk for `agent-bootstrap.toml`.
5. **Minimal deps.** v0 requires only `python-frontmatter` and `PyYAML` (the `.[core]` extra). No Click/Typer — argparse matches existing CLIs and adds zero deps.
6. **Progressive disclosure.** `engram --help` shows the most useful commands first. Advanced commands appear in later versions.

### Dependency strategy
- **v0:** `.[core]` only (frontmatter, yaml). Zero new deps beyond what's already needed.
- **Semantic search:** Optional via `.[search]`. CLI auto-detects and falls back gracefully.
- **TUI features (v2 review):** Optional via a future `.[cli]` extra if we add a TUI library.

### Testing strategy
- Unit tests per command module (test_cli_validate.py, etc.)
- Integration tests via subprocess invocation against a fixture repo
- Existing 190+ tests must continue passing (no regressions)
- Pre-commit hook compatibility verified in the integration phase
