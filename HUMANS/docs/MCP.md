# Engram MCP Architecture Guide

This document explains the Model Context Protocol (MCP) layer in the Engram memory system: what it exposes, why it exists, and how it fits the larger design.

- If you want a quick setup path, read [QUICKSTART.md](QUICKSTART.md).
- If you want the big-picture system rationale, read [CORE.md](CORE.md).
- If you want deeper theory and future directions, read [DESIGN.md](DESIGN.md).
- If you want worktree deployment, read [WORKTREE.md](WORKTREE.md).
- If you want third-party tool integrations, read [INTEGRATIONS.md](INTEGRATIONS.md).
- If something breaks, read [HELP.md](HELP.md).

---

## What the MCP layer is

The MCP layer is the repo's tool-facing interface.

The memory system's source of truth is still the Git repository itself: Markdown files, summaries, governance files, and Git history. MCP does not replace that file-based design. It packages the same system behind a cleaner contract so tool-using clients can read memory, inspect provenance, and perform governed writes without each client reimplementing the repo's rules.

In plain language:

- The repo is the memory.
- Git is the history and recovery mechanism.
- MCP is the safe operating interface.

The default architectural entry point for a new session remains `README.md`. After that initial orientation, `core/INIT.md` handles live routing and `core/memory/HOME.md` is the session entry point for normal returning sessions unless the router points somewhere more specific.

That separation is intentional. It keeps the system portable and inspectable while still making it ergonomic for modern agent runtimes.

## Implementation files

These files define the MCP setup:

| File | Role |
| --- | --- |
| `core/tools/memory_mcp.py` | Compatibility entrypoint script — the simplest path-based way to launch the server. |
| `core/tools/agent_memory_mcp/server.py` | Runtime bootstrap — builds the FastMCP server, resolves the repo root, registers all tools, resources, and prompts. |
| `core/tools/agent_memory_mcp/server_main.py` | CLI entrypoint for `engram-mcp` command (installed via `pip install -e .[server]`). |
| `core/tools/agent_memory_mcp/tools/read_tools.py` | Tier 0 — read-only inspection, analysis, and reporting tools. |
| `core/tools/agent_memory_mcp/tools/semantic/` | Tier 1 — semantic write tools split by domain: `graph_tools.py`, `knowledge_tools.py`, `plan_tools.py`, `session_tools.py`, `skill_tools.py`, `user_tools.py`. |
| `core/tools/agent_memory_mcp/tools/write_tools.py` | Tier 2 — raw fallback mutation tools, gated behind `MEMORY_ENABLE_RAW_WRITE_TOOLS`. |
| `HUMANS/tooling/agent-memory-capabilities.toml` | Capability manifest — declares tools, approval classes, tool profiles, error taxonomy, and resource/prompt metadata. |
| `HUMANS/tooling/mcp-config-example.json` | Example client config for Claude Desktop and other MCP hosts. |
| `.codex/config.toml` | Project-scoped Codex MCP config using portable relative paths. |

## How the server is launched

The canonical path-based script is:

```bash
python core/tools/memory_mcp.py
```

That wrapper imports the repo-local server and runs it. When the package is installed, prefer the CLI entrypoint instead:

```bash
engram-mcp
```

### How the repo root is resolved

The runtime supports three ways to find the memory repository:

1. An explicit `repo_root` argument when embedding the server from Python.
2. The `MEMORY_REPO_ROOT` environment variable.
3. The `AGENT_MEMORY_ROOT` environment variable.

If none of those are set, the runtime falls back to file-relative detection from the installed server code.

### Practical setup patterns

**Run it from the repo itself**

```bash
cd Engram
python core/tools/memory_mcp.py
```

**Run it from somewhere else**

```bash
MEMORY_REPO_ROOT=/path/to/Engram python /path/to/Engram/core/tools/memory_mcp.py
```

**Embed it in Python**

```python
from engram_mcp.agent_memory_mcp.server import create_mcp

mcp, tools, root, repo = create_mcp(repo_root="/path/to/Engram")
```

### Client configuration example

The repo includes an example config in `HUMANS/tooling/mcp-config-example.json`. A minimal configuration for Claude Desktop or any MCP-capable host:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": ["C:/path/to/Engram/core/tools/memory_mcp.py"],
      "env": {
        "AGENT_MEMORY_ROOT": "C:/path/to/Engram"
      }
    }
  }
}
```

What this does:

- launches the repo-local MCP wrapper script,
- tells the runtime which memory repo to operate on,
- lets the desktop client discover the governed tool surface from the server and capability manifest.

The client owns the UI and approval flow; the repo-local server owns the repo-specific behavior.

For worktree deployments, set `MEMORY_REPO_ROOT` to the worktree path and `HOST_REPO_ROOT` to the host repo root. See [WORKTREE.md](WORKTREE.md) for details.

---

## Tool surface

The MCP server exposes **95+ tools** organized into three tiers. The tier system enforces a deliberate preference order: inspect before mutating, use semantic operations before raw edits, and gate low-level writes behind an explicit opt-in.

### Tier 0: Read-only tools

These tools inspect, analyze, and report on the repo without changing it. Always available.

**Capability and policy introspection**

| Tool | Description |
| --- | --- |
| `memory_get_capabilities` | Return the governed capability manifest as structured JSON. |
| `memory_get_tool_profiles` | Return advisory tool-profile metadata for host-side narrowing. |
| `memory_get_policy_state` | Compile the current governed contract for an operation and optional path. |
| `memory_route_intent` | Recommend the best governed operation for a natural-language intent. |

**File and repo inspection**

| Tool | Description |
| --- | --- |
| `memory_read_file` | Read a file with parsed frontmatter and version token. |
| `memory_list_folder` | List folder contents. |
| `memory_search` | Full-text search across the repo. |
| `memory_resolve_link` | Resolve one markdown-style link target relative to a governed source path. |
| `memory_find_references` | Return structured references to a path across governed markdown. |
| `memory_scan_frontmatter_health` | Scan markdown frontmatter and headings for cross-reference health issues. |
| `memory_validate_links` | Validate internal markdown and frontmatter path references. |
| `memory_review_unverified` | Return a grouped digest of `_unverified/` knowledge files. |
| `memory_get_file_provenance` | Return provenance and trust metadata for a file. |
| `memory_inspect_commit` | Inspect a specific commit by SHA. |
| `memory_diff` | Show the diff for a specific commit or range. |
| `memory_diff_branch` | Compare the current branch against a base branch. |
| `memory_git_log` | Return recent commit history. |

**Analysis and reporting**

| Tool | Description |
| --- | --- |
| `memory_generate_summary` | Generate a paste-ready SUMMARY.md draft for a folder. |
| `memory_generate_names_index` | Generate a structured NAMES.md payload for knowledge files. |
| `memory_check_cross_references` | Scan for broken links and SUMMARY drift. |
| `memory_surface_unlinked` | Surface knowledge files with zero or low cross-reference connectivity. |
| `memory_suggest_links` | Return scored cross-reference suggestions for one governed markdown file, with optional same-domain or cross-domain filtering. |
| `memory_cross_domain_links` | Summarize cross-domain link flow, with optional domain and edge-count filters. |
| `memory_link_delta` | Diff the current link surface against a git base ref, with optional cross-domain and transition filters. |
| `memory_reorganize_preview` | Preview the impact of moving a file or subtree. |
| `memory_suggest_structure` | Suggest advisory structure improvements for the governed markdown tree. |
| `memory_analyze_graph` | Compute structural metrics on the knowledge graph (degree, density, clusters, orphans). |

### Cross-reference ergonomics

These read-only tools are designed for agents that need to reason about markdown links before writing anything:

- `memory_resolve_link`: validate how a raw target resolves from a source file, including anchors.
- `memory_scan_frontmatter_health`: catch malformed frontmatter and broken `related:` entries before graph tools fail downstream.
- `memory_suggest_links`: propose scored candidate targets for one file using graph structure plus text cues, optionally narrowed to `all`, `same`, or `cross` domain suggestions and a minimum score threshold.
- `memory_cross_domain_links`: summarize how domains connect to each other, optionally narrowed by source domain, target domain, or minimum edge count.
- `memory_link_delta`: compare the current graph to a base ref such as `HEAD` and explain what changed.

Example `memory_suggest_links` use case:

```json
{
  "path": "memory/knowledge/philosophy/compression.md",
  "max_suggestions": 5,
  "domain_mode": "cross",
  "min_score": 2.0
}
```

Example `memory_cross_domain_links` use case:

```json
{
  "path": "memory/knowledge",
  "source_domain": "philosophy",
  "target_domain": "cognitive-science",
  "min_edge_count": 2
}
```

Example `memory_link_delta` use cases:

```json
{
  "path": "memory/knowledge",
  "base_ref": "HEAD",
  "cross_domain_only": true,
  "transition_filter": "connected->sink"
}
```

Important output fields:

- `domain_mode`: echoes whether `memory_suggest_links` returned `all`, `same`, or `cross` domain candidates.
- `min_score`: suppresses low-confidence `memory_suggest_links` candidates below the requested score.
- `target_domain` / `is_same_domain`: help agents apply suggestion results directly without re-parsing paths.
- `source_domain_filter` / `target_domain_filter`: echo the applied `memory_cross_domain_links` pair filters.
- `min_edge_count`: suppress low-volume domain pairs below the requested threshold.
- `added_domain_pairs` / `removed_domain_pairs`: aggregate edge deltas by source and target domain.
- `changed_category_counts`: count how many files changed connectivity class, for example `isolated->connected`.
- `impacted_files_detail`: per-file view of domain, previous category, and current category.
- `cross_domain_only`: when true, only cross-domain edge changes are retained in the response.
- `transition_filter`: when set, only impacted files and edges matching that category transition are retained.

**Health and governance**

| Tool | Description |
| --- | --- |
| `memory_session_health_check` | Return session-start maintenance status for ACCESS and review queue. |
| `memory_validate` | Run system integrity checks (frontmatter, structure, ACCESS format). |
| `memory_access_analytics` | Classify files using curation-policy ACCESS patterns (hot, cold, rising, etc.). |
| `memory_check_knowledge_freshness` | Check knowledge-file freshness against the configured host repo. |
| `memory_check_aggregation_triggers` | Check whether aggregation thresholds have been reached. |
| `memory_aggregate_access` | Analyze accumulated ACCESS data without mutating. |
| `memory_audit_trust` | Audit trust decay and anomaly signals across the repo. |
| `memory_get_maturity_signals` | Return current maturity stage indicators. |
| `memory_run_periodic_review` | Run a periodic review analysis (read-only reporting). |
| `memory_list_plans` | List active plans and their next actions. |
| `memory_list_pending_reviews` | List knowledge files pending review. |
| `memory_reset_session_state` | Reset session state files (scratchpad, working state). |

### Tier 1: Semantic write tools

These are the normal write path. Each tool represents a bounded operation with built-in invariants and an automatic commit on success. They are not generic file-edit tools — each one owns a narrow slice of the memory model and keeps related files in sync.

**Plans**

| Tool | Description |
| --- | --- |
| `memory_plan_create` | Create a new structured plan with phases, sources, postconditions, and an optional budget. |
| `memory_plan_execute` | Inspect, start, complete, or record failure on a plan phase; surfaces sources, approval gates, budget status, and verification results. |
| `memory_plan_verify` | Evaluate a phase's postconditions without modifying plan state. Returns per-postcondition results and a pass/fail summary. |
| `memory_plan_review` | Scan completed plans or export completed-plan artifacts. |
| `memory_record_trace` | Emit a trace span to the session's TRACES.jsonl file. Non-blocking; always returns span_id on success. |
| `memory_query_traces` | Query trace spans across sessions or date ranges. Returns spans (newest-first) with aggregates. |
| `memory_plan_briefing` | Return a single-call briefing packet for a requested or next-actionable phase, including source excerpts, failures, recent traces, approval state, and context-budget metadata. |
| `memory_stage_external` | Stage externally fetched content into a project `IN/` folder with governed frontmatter, URL sanitization, and per-project SHA-256 deduplication. |
| `memory_scan_drop_zone` | Scan configured `[[watch_folders]]` entries from `agent-bootstrap.toml` and bulk-stage new `.md`, `.txt`, or `.pdf` content into project inboxes. |
| `memory_run_eval` | Run declarative offline eval scenarios from `memory/skills/eval-scenarios/` and record compact eval summary spans. |
| `memory_eval_report` | Read historical eval runs from trace spans and aggregate summary metrics and trends. |
| `memory_register_tool` | Register or update an external tool definition in the tool registry. Returns action ("created"\|"updated") and registry_file path. |
| `memory_get_tool_policy` | Query the tool registry by tool name, provider, tags, or cost tier. Returns matching definitions. |
| `memory_request_approval` | Create a pending approval document for a plan phase and pause the plan. Returns approval_file, expires, and plan_status. |
| `memory_resolve_approval` | Approve or reject a pending approval. Moves document to resolved/, updates plan status to active (approve) or blocked (reject). |

**`memory_plan_create` key parameters**

| Parameter | Type | Description |
| --- | --- | --- |
| `phases` | list | Phase dicts. Each phase may include `sources` (list of `{path, type, intent, uri?}`), `postconditions` (list of strings or `{description, type?, target?}`), and `requires_approval` (bool). |
| `budget` | dict \| null | Optional budget: `deadline` (YYYY-MM-DD), `max_sessions` (int ≥ 1), `advisory` (bool, default `true`). |

The `resulting_state` includes a `budget_status` block when a budget is set.

**`memory_plan_execute` actions and response fields**

| Action | Effect | Key response fields |
| --- | --- | --- |
| `inspect` | Read-only: returns full phase payload. | `phase.sources`, `phase.postconditions`, `phase.failures`, `phase.attempt_number`, `phase.requires_approval`, `budget_status` |
| `start` | Transitions phase to `in-progress`. | `sources`, `postconditions`, `requires_approval`, `approval_required`, `budget_status` |
| `complete` | Seals phase; increments `sessions_used`; emits budget warnings when limits are approached. When `verify=true`, evaluates postconditions first and blocks completion on failure. | `sessions_used`, `budget_status`, `warnings`, `verification_results` (when verify=true) |
| `record_failure` | Appends a `PhaseFailure` entry to the phase (timestamp, reason, optional verification_results). | `failures`, `attempt_number` |

`advisory: true` budgets emit warnings only. `advisory: false` budgets raise an error when the session cap is exceeded.

**`memory_plan_verify` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `plan_id` | str | Plan identifier. |
| `phase_id` | str | Phase to verify. |
| `project_id` | str \| null | Optional project scope. |

Returns `verification_results` (per-postcondition status/detail), `summary` (total/passed/failed/skipped/errors counts), and `all_passed` (bool). Four validator types: `check` (file existence), `grep` (pattern::path regex search), `test` (allowlisted shell command, requires `ENGRAM_TIER2=1`), `manual` (always skipped).

**`memory_record_trace` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `session_id` | str | Session path, e.g. `memory/activity/2026/04/01/chat-001`. |
| `span_type` | str | One of: `tool_call`, `plan_action`, `retrieval`, `verification`, `guardrail_check`. |
| `name` | str | Human-readable operation name (e.g. `"complete"`, `"memory_plan_execute"`). |
| `status` | str | One of: `ok`, `error`, `denied`. |
| `duration_ms` | int \| null | Wall-clock duration in milliseconds. |
| `metadata` | dict \| null | Type-specific context (sanitized: no secrets, strings truncated at 200 chars, max 2 KB). |
| `cost` | dict \| null | Token counts: `{tokens_in, tokens_out}`. |
| `parent_span_id` | str \| null | Parent span ID for nested operations. |

Returns `{span_id, trace_file, status}`. `trace_file` is the TRACES.jsonl path for the session. Plan tools (create, start, complete, record_failure, verify) emit `plan_action` and `verification` spans automatically when a `session_id` is available.

**`memory_query_traces` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `session_id` | str \| null | Exact session to query. |
| `date_from` | str \| null | Start date (YYYY-MM-DD, inclusive). |
| `date_to` | str \| null | End date (YYYY-MM-DD, inclusive). |
| `span_type` | str \| null | Filter by span type. |
| `plan_id` | str \| null | Filter by `metadata.plan_id`. |
| `status` | str \| null | Filter by status. |
| `limit` | int | Max spans to return (default 100). |

Returns `{spans, total_matched, aggregates: {total_duration_ms, by_type, by_status, error_rate}}`.

**`memory_plan_briefing` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `plan_id` | str | Plan identifier. |
| `phase_id` | str \| null | Optional phase to brief on. Defaults to the next actionable phase. |
| `project_id` | str \| null | Optional project scope. |
| `max_context_chars` | int | Character budget for assembled context (default 8000, 0 = unlimited). |
| `include_sources` | bool | Include source-file contents and excerpts. |
| `include_traces` | bool | Include recent trace spans for the plan. |
| `include_approval` | bool | Include approval document state when applicable. |

Returns a single packet with `{plan_id, project_id, phase_id, phase, source_contents, failure_summary, recent_traces, approval_status, context_budget}`. When no actionable phase exists and `phase_id` is omitted, the tool returns a read-only plan summary with progress instead. If `MEMORY_SESSION_ID` is present, the tool records a `tool_call` trace span named `memory_plan_briefing`.

**`memory_stage_external` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `project` | str | Target project slug. Content is staged under `memory/working/projects/{project}/IN/`. |
| `filename` | str | Basename for the staged file. Path separators and traversal segments are rejected. |
| `content` | str | Non-empty UTF-8 text content to persist. Limited to 500,000 characters. |
| `source_url` | str | Original external URL. Query strings and fragments are stripped before persistence. |
| `fetched_date` | str | Source fetch date in `YYYY-MM-DD` format. |
| `source_label` | str | Human-readable source label written into frontmatter. |
| `dry_run` | bool | When true, return the preview envelope without writing the file. |

Returns `{action, project, target_path, frontmatter_preview, content_chars, content_hash, duplicate, staged}`. The tool always computes a SHA-256 content hash and checks `memory/working/projects/{project}/.staged-hashes.jsonl` before writing; duplicate content raises `DuplicateContentError`. Successful writes are direct project-inbox writes, not auto-commit operations. When `MEMORY_SESSION_ID` is present, the tool records a trace span for self-instrumentation.

**`memory_scan_drop_zone` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `project_filter` | str \| null | Optional project slug; when set, scan only matching `[[watch_folders]]` entries. |

The tool reads `[[watch_folders]]` from `agent-bootstrap.toml`. Supported keys per entry are `path`, `target_project`, `source_label`, `extensions`, and `recursive`. Relative paths resolve from the repo root. Watch folders inside the Engram repository are rejected so the scanner cannot ingest tracked repo files back into itself.

Returns `{folders_scanned, files_found, staged_count, duplicate_count, error_count, items}`. Each `items` entry includes `{filename, target_project, outcome, hash, error_message}` where `outcome` is `staged`, `duplicate`, or `error`. `.pdf` files are extracted with `pypdf` first and `pdfminer.six` second; if neither library is available, the tool records a per-file error and continues scanning the remaining inputs. When `MEMORY_SESSION_ID` is present, the tool records a trace span for self-instrumentation.

**`memory_run_eval` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `session_id` | str | Session path where eval summary spans should be recorded. |
| `scenario_id` | str \| null | Optional single scenario slug to run. |
| `tag` | str \| null | Optional tag filter; runs all matching scenarios. |

Scenarios are loaded from `memory/skills/eval-scenarios/` and executed in isolated temporary directories. Only compact summary spans are written back to the live trace tree, one per scenario, with `name: eval:{scenario_id}` and metric metadata.

`memory_run_eval` is gated behind `ENGRAM_TIER2=1` because scenarios may invoke verification on `test`-type postconditions. Returns `{results, summary, metrics}` and echoes `scenario_id` or `tag` when provided.

**`memory_eval_report` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `date_from` | str \| null | Start date (YYYY-MM-DD, inclusive). |
| `date_to` | str \| null | End date (YYYY-MM-DD, inclusive). |
| `scenario_id` | str \| null | Optional single scenario slug filter. |

Returns `{runs, summary, metrics, trends}` sourced from existing `eval:*` trace spans. `summary` reports total/pass/fail/error counts, `metrics` reports mean values across matching runs, and `trends` includes `{first, last, delta}` for metrics when at least two runs are available.

**`memory_register_tool` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `name` | str | Tool identifier — kebab-case slug (required). |
| `description` | str | What the tool does (required). |
| `provider` | str | Provider group slug: `shell`, `api`, `mcp-external`, etc. (required). |
| `approval_required` | bool | Whether invocation requires human approval (default false). |
| `cost_tier` | str | `free` \| `low` \| `medium` \| `high` (default `free`). |
| `schema` | dict \| null | JSON Schema for tool inputs. |
| `rate_limit` | str \| null | Human-readable rate limit (e.g. `"100/day"`). |
| `timeout_seconds` | int | Expected invocation timeout (default 30). |
| `tags` | list[str] \| null | Categorization tags (e.g. `["lint", "test"]`). |
| `notes` | str \| null | Usage notes, gotchas, or warnings. |

Returns `{tool_name, provider, registry_file, action}` where `action` is `"created"` or `"updated"`. SUMMARY.md at `memory/skills/tool-registry/SUMMARY.md` is regenerated on every call.

**`memory_get_tool_policy` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `tool_name` | str \| null | Exact tool name (returns at most one result). |
| `provider` | str \| null | Filter by provider group. |
| `tags` | list[str] \| null | Filter by tags (any-match). |
| `cost_tier` | str \| null | Filter by cost tier. |

At least one filter parameter is required. Returns `{tools: [...], count}`. An empty result is not an error. Each tool entry includes `provider`, `name`, `description`, `approval_required`, `cost_tier`, `timeout_seconds`, and optional `schema`, `rate_limit`, `tags`, `notes`.

**`memory_request_approval` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `plan_id` | str | Plan slug. |
| `phase_id` | str | Phase slug. Phase must be `pending` or `in-progress`. |
| `project_id` | str \| null | Optional; inferred if unambiguous. |
| `context` | str \| null | Additional context appended to auto-generated phase summary. |
| `expires_days` | int | Days until expiry (default 7). |

Creates a YAML approval document at `memory/working/approvals/pending/{plan_id}--{phase_id}.yaml` and sets `plan.status = "paused"`. If a pending approval already exists, returns the existing document without creating a duplicate. Returns `{approval_file, status: "pending", expires, plan_status: "paused"}`.

**`memory_resolve_approval` parameters and response**

| Parameter | Type | Description |
| --- | --- | --- |
| `plan_id` | str | Plan slug. |
| `phase_id` | str | Phase slug. |
| `resolution` | str | `"approve"` or `"reject"`. |
| `comment` | str \| null | Optional reviewer comment. |

Moves the approval document from `pending/` to `resolved/`, sets `plan.status = "active"` (approve) or `"blocked"` (reject), and regenerates `working/approvals/SUMMARY.md`. Errors if no pending approval document exists. Returns `{approval_file, status, plan_status}`.

**Approval lifecycle**

Plan statuses now include `paused` (awaiting human approval), in addition to `draft`, `active`, `blocked`, `completed`, and `abandoned`. Transitions: `active` → `paused` (approval requested), `paused` → `active` (approved), `paused` → `blocked` (rejected or expired). Expiry is lazy: checked on read of the approval document; expired approvals move to `resolved/` with `status: expired`. `memory_plan_execute` with `action: "start"` on a `requires_approval` phase automatically invokes the approval creation logic if no document exists.

**Knowledge lifecycle**

| Tool | Description |
| --- | --- |
| `memory_add_knowledge_file` | Create a new knowledge file with proper frontmatter. |
| `memory_promote_knowledge` | Move a file from `_unverified/` to a verified domain folder. |
| `memory_promote_knowledge_batch` | Batch promotion of multiple knowledge files. |
| `memory_promote_knowledge_subtree` | Promote an entire subtree of knowledge files. |
| `memory_demote_knowledge` | Move knowledge to a lower trust tier. |
| `memory_archive_knowledge` | Archive knowledge files to historical storage. |
| `memory_mark_reviewed` | Mark a knowledge file as reviewed. |
| `memory_update_names_index` | Update the NAMES.md index for a knowledge folder. |
| `memory_reorganize_path` | Move or reorganize knowledge within the tree. |
| `memory_prune_redundant_links` | Remove redundant cross-references from knowledge files. |

**Session and activity**

| Tool | Description |
| --- | --- |
| `memory_record_session` | Record a full session: summary, reflection, and access entries. |
| `memory_record_chat_summary` | Record a single chat session summary to the activity log. |
| `memory_record_reflection` | Record a session reflection entry. |
| `memory_log_access` | Log a single memory file access event to ACCESS.jsonl. |
| `memory_log_access_batch` | Log multiple access events in a batch. |
| `memory_run_aggregation` | Aggregate hot ACCESS logs into summary updates. |

**Scratchpad, skills, and identity**

| Tool | Description |
| --- | --- |
| `memory_append_scratchpad` | Append a section to the session scratchpad (CURRENT.md). |
| `memory_update_skill` | Update a skill definition in the skills folder. |
| `memory_update_user_trait` | Update a user trait in the identity file. |

**Governance and safety**

| Tool | Description |
| --- | --- |
| `memory_flag_for_review` | Flag a file or item for the review queue. |
| `memory_resolve_review_item` | Resolve a flagged review item. |
| `memory_record_periodic_review` | Record a periodic review cycle. |
| `memory_revert_commit` | Revert a memory commit with preview-first flow. |

### Tier 2: Raw fallback tools

Low-level mutation tools for operations that don't yet have a dedicated semantic tool. **Not enabled by default** — the server only exposes them when the runtime explicitly sets `MEMORY_ENABLE_RAW_WRITE_TOOLS=1`.

| Tool | Description |
| --- | --- |
| `memory_write` | Create or overwrite a file and stage it (no auto-commit). |
| `memory_edit` | Exact string replacement in a file, then stage (no auto-commit). |
| `memory_delete` | Delete a file and stage the removal (no auto-commit). |
| `memory_move` | Rename or move a file, preserving git history (git mv). |
| `memory_update_frontmatter` | Merge key-value pairs into a file's YAML frontmatter. |
| `memory_update_frontmatter_bulk` | Apply frontmatter updates to multiple files as a single staged transaction. |
| `memory_commit` | Commit all staged changes as a single atomic commit. |

Tier 2 tools use a **staged-transaction model**: mutations are staged in git's index without committing, and `memory_commit` seals them as a single atomic commit. They reject protected directories such as `memory/users/`, `governance/`, `memory/activity/`, and `memory/skills/`.

### Semantic search (optional)

When the `sentence-transformers` package is installed (`pip install agent-memory-mcp[search]`), two additional tools become available:

| Tool | Description |
| --- | --- |
| `memory_semantic_search` | Hybrid vector + BM25 search with freshness and helpfulness reranking. Accepts `query`, optional `scope`, `limit`, `min_trust`, and tunable weights (`vector_weight`, `bm25_weight`, `freshness_weight`, `helpfulness_weight`). |
| `memory_reindex` | Force a full or incremental rebuild of the embedding index. |

The embedding index is stored in `.engram/search.db` (gitignored) and is built lazily on first search. It indexes all `.md` files under `memory/knowledge/`, `memory/skills/`, and `memory/users/`, using the `all-MiniLM-L6-v2` model (384 dimensions, local-only — no external API calls). Files are re-embedded only when their modification time changes.

Hybrid scoring combines four signals with configurable weights (defaults in parentheses):
- **Vector similarity** (0.4) — cosine similarity between query and chunk embeddings
- **BM25** (0.3) — classical keyword relevance
- **Freshness** (0.15) — exponential decay from `last_verified` or `created` date (180-day half-life)
- **Helpfulness** (0.15) — mean helpfulness from ACCESS.jsonl retrieval logs

---

## MCP resources

The server exposes four MCP resources — stable read endpoints that clients can bind to without making tool calls:

| URI | Backed by | Description |
| --- | --- | --- |
| `memory://capabilities/summary` | `memory_get_capabilities` | Load the compact capability and profile snapshot. |
| `memory://policy/summary` | `memory_get_policy_state` | Inspect change-class, fallback, and profile policy boundaries. |
| `memory://session/health` | `memory_session_health_check` | Check aggregation pressure, review cadence, and pending queue state. |
| `memory://plans/active` | `memory_list_plans` | Load a compact summary of active plans and next actions. |

Resources are passive — they provide data the client can read at any time, like a status dashboard. They complement the tools (which perform actions) and prompts (which scaffold workflows).

## MCP prompts

The server exposes four MCP prompts — reusable workflow scaffolds that guide the agent through recurring multi-step operations:

| Prompt | Backed by | Description |
| --- | --- | --- |
| `memory_prepare_unverified_review_prompt` | `memory_review_unverified` | Guide review of low-trust knowledge before promotion. |
| `memory_governed_promotion_preview_prompt` | `memory_promote_knowledge_batch` | Structure a governed promotion-preview conversation. |
| `memory_prepare_periodic_review_prompt` | `memory_prepare_periodic_review` | Guide a protected periodic-review workflow. |
| `memory_session_wrap_up_prompt` | `memory_record_session` | Guide end-of-session summarization, reflection, and deferred follow-up. |

Prompts are useful for MCP-native clients that support prompt discovery: the client can offer them as one-click workflows, or the agent can invoke them as structured conversation templates.

---

## Tool profiles

The capability manifest defines three advisory profiles for host-side tool narrowing:

| Profile | Includes | When to use |
| --- | --- | --- |
| `full` | All tiers (0 + 1 + 2), resources, prompts | Full governed access with raw fallback enabled. |
| `guided_write` | Tier 0 + Tier 1, resources, prompts | Normal operation — governed reads and semantic writes. No raw fallback. |
| `read_only` | Tier 0 only, resources | Inspection and reporting only. No mutation. |

Profiles are advisory — the server exposes all registered tools regardless. The host client is responsible for filtering the tool surface based on the selected profile. The `memory_get_tool_profiles` tool returns the profile metadata programmatically.

The **default** experience is `guided_write`: all Tier 0 and Tier 1 tools are available, Tier 2 is hidden. Setting `MEMORY_ENABLE_RAW_WRITE_TOOLS=1` enables the `full` profile.

## The manifest

The file `HUMANS/tooling/agent-memory-capabilities.toml` is not just documentation. It is part of the runtime contract.

It tells a client:

- which tools exist and which tier they belong to,
- whether the runtime is read-only, semantic-capable, or full,
- which operations are `automatic`, `proposed`, or `protected`,
- which files each semantic operation is allowed to own,
- how previews and approvals should work,
- which tool profiles are available for host-side narrowing,
- which MCP resources and prompts are registered,
- which error types the server may return (`ConflictError`, `NotFoundError`, `ValidationError`, `StagingError`, `MemoryPermissionError`, `AlreadyDoneError`),
- how results should be presented and which fallback behavior is acceptable.

This matters because the system is deliberately hybrid. The desktop or host application is expected to discover capabilities and enforce approval UX, while the repo-local MCP server is expected to execute the repo-specific logic correctly.

The manifest makes that split explicit instead of relying on undocumented conventions.

---

## Design principles

### 1. The repo stays canonical

The MCP layer is an interface, not a second storage system.

That preserves the project's core bet: memory should live in files the user owns, can diff, can back up, and can move across tools. MCP improves access; it does not become the source of truth.

### 2. Semantic operations come before raw edits

The preferred path is always a named operation that understands the memory model.

For example, recording a periodic review is not treated as an arbitrary edit to `governance/` files. It is a specific semantic action with bounded ownership, protected approval, expected commit metadata, and known result fields.

This reduces the chance of partial updates, broken invariants, or accidental policy drift.

### 3. Approval boundaries are part of the protocol

The MCP surface classifies writes as:

- **`automatic`** — Routine, bounded writes with no approval needed (e.g. ACCESS logging, scratchpad append).
- **`proposed`** — Meaningful changes requiring user awareness before write (e.g. knowledge promotion, identity updates).
- **`protected`** — Changes to governance, skills, or system-level files requiring explicit approval.

That mirrors the broader governance model of the repo. Safety is not left to prompt wording alone — it is encoded in the operation model.

### 4. Responsibility is split cleanly

The manifest defines a hybrid boundary:

- The host client owns approval UX, capability discovery, preview rendering, and fallback selection.
- The repo-local MCP server owns semantic execution, repo-specific invariants, schema validation, and authoritative mutation.

This prevents the client from needing to understand every repo rule while also preventing the repo server from trying to be a full user interface.

### 5. Git is the publication layer

The server does not merely edit files. Governed semantic tools publish changes through Git and return structured publication metadata (commit SHA, changed files, new state).

That fits the larger system philosophy: memory changes should be reviewable, provenance should be inspectable, commits should be attributable, and reverts should be possible.

### 6. Degradation is deliberate

The architecture distinguishes among:

- full semantic MCP,
- read-only governed preview,
- raw fallback or defer.

That is consistent with the rest of the system, which is designed to degrade gracefully instead of pretending unavailable capabilities worked. If the runtime cannot safely perform a governed write, it should preview, defer, or report the block honestly.

### 7. Read-first governance is intentional

The read tools outnumber the write tools by design. Governance should become more observable before it becomes more automated. The system wants good inspection paths, provenance checks, periodic review reports, and maturity signals so that high-leverage writes remain understandable and auditable.

---

## How MCP fits the philosophy of the whole system

The MCP architecture is not a sidecar. It expresses the same design philosophy found throughout the repo.

**Portability without abandoning ergonomics.** The whole system is built around model-agnostic, file-based memory. MCP makes that practical for tool-using runtimes by exposing the repo through a standard protocol, but the memory remains portable even without MCP. A vendor-specific memory API would be convenient but would weaken the ownership and portability story. MCP gives interoperability without changing the core storage model.

**Transparency and human control.** Human-readable files, Git history, capability manifests, approval classes, and structured write results all point in the same direction: the user should be able to understand what the system can do and what it just did. This is the opposite of opaque built-in memory features that silently rewrite state behind the scenes.

**Safety as structure.** The wider design separates informational memory from procedural authority and places high-leverage surfaces behind tighter governance. The MCP layer reflects that exactly: protected directories are not open to raw writes, semantic tools are bounded by domain, approval classes are explicit, external content flows through constrained workflows, and system-level review writes are narrow and protected.

**Context efficiency.** One purpose of MCP is to let runtimes ask targeted questions instead of loading large parts of the repo speculatively. A client can ask for maturity signals, provenance, or a periodic review report directly rather than reading several governance files and reconstructing the answer itself. That is aligned with the project's strong preference for progressive disclosure and metadata-first retrieval.

**Graceful degradation.** The broader system never assumes ideal capabilities. The MCP architecture follows the same rule by making read-only mode, deferred action, and fallback behavior part of the declared contract. That makes the system more honest and more robust across different platforms.

---

## What the MCP layer is not

To keep expectations clear, the MCP server is not:

- a replacement for reading the repo's core documents,
- a full agent runtime,
- a hidden database behind the Markdown,
- permission to bypass governance,
- a general-purpose unrestricted file editor.

It is a structured interface over a governed Git-backed memory system.

## Recommended mental model

1. The repository defines the memory model.
2. The manifest describes the operating contract.
3. The FastMCP server exposes that contract to clients through tools, resources, and prompts.
4. Semantic tools enforce the repo's invariants.
5. Git records and publishes the resulting state.

That is why the MCP layer fits this project so naturally. It gives the repo a usable systems interface without giving up the project's core commitments: transparency, safety, portability, and human control.
