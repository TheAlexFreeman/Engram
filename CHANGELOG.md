# Changelog

This file records how the memory system's own structure, rules, and governance have changed over time. It is not a log of content changes (what the user said or learned) but of **system changes** (how memory is organized, stored, retrieved, and curated).

Each entry should explain not just what changed, but **why** — so that future agents can understand the evolutionary trajectory of this system and make informed decisions about further modifications.

## Format

```
## [YYYY-MM-DD] Brief title

**Changed:** What was modified, added, or removed.
**Reasoning:** Why this change was made — what problem it solves or what improvement it enables.
**Approved by:** "user" if explicitly approved, "agent (pending review)" if auto-applied and awaiting confirmation.
```

---

## Records

## [2026-03-27] Phase 9: External ingestion affordances

**Changed:** Added the Phase 9 external-intake layer for plan execution and project research staging.

- **`SourceSpec` and `phase_payload()` in `core/tools/agent_memory_mcp/plan_utils.py`** — `SourceSpec` now supports `mcp_server`, `mcp_tool`, and `mcp_arguments` for `type: mcp` sources. `phase_payload()` now emits `fetch_directives` and `mcp_calls` for missing external and MCP-backed sources so agents can fetch prerequisite context before starting work.
- **`stage_external_file()` and `scan_drop_zone()`** — new helpers in `plan_utils.py`. `stage_external_file()` writes project-local inbox files under `memory/working/projects/{project}/IN/` with enforced `source: external-research`, `trust: low`, sanitized `origin_url`, and a per-project `.staged-hashes.jsonl` SHA-256 registry. `scan_drop_zone()` reads `[[watch_folders]]` from `agent-bootstrap.toml`, stages supported `.md`, `.txt`, and `.pdf` files, and returns a structured scan report with staged, duplicate, and error counts.
- **`memory_stage_external` / `memory_scan_drop_zone`** — new MCP tools in `plan_tools.py`. `memory_stage_external` supports preview-first via `dry_run`, while `memory_scan_drop_zone` bulk-processes configured watch folders and degrades gracefully when PDF extraction libraries are unavailable.
- **Tests and docs** — expanded schema/helper coverage and MCP integration coverage for both new tools, finalized the Phase 9 project design docs, documented the tools in `HUMANS/docs/MCP.md`, added the ingestion workflow to `HUMANS/docs/INTEGRATIONS.md`, and registered the new capabilities in `HUMANS/tooling/agent-memory-capabilities.toml`.

**Reasoning:** Earlier harness phases made sources and phase context first-class, but the system still lacked a governed path for turning fetched external material into project-local artifacts. Phase 9 closes that gap by making external intake explicit, deduplicated, and discoverable in both the plan payload contract and the MCP tool surface.

**Approved by:** user

## [2026-03-27] Phase 8: Context assembly briefing packet

**Changed:** Added the Phase 8 context-assembly layer for plan execution.

- **`assemble_briefing()` in `core/tools/agent_memory_mcp/plan_utils.py`** — new helper that composes `phase_payload()` with source-file excerpts, failure summaries, approval status, recent trace spans, and context-budget accounting. Internal sources degrade gracefully when files are missing, and the source allocator truncates via smart head/tail excerpts within a configurable `max_context_chars` budget.
- **`memory_plan_briefing`** — new read-only MCP tool in `plan_tools.py`. It returns a single-call briefing packet for a requested phase or, when `phase_id` is omitted, for the next actionable phase. If no actionable phase exists, it returns a plan summary instead. When `MEMORY_SESSION_ID` is present, the tool records a self-instrumentation `tool_call` trace span.
- **Tests** — expanded schema-level coverage with `TestAssembleBriefing` and added MCP integration tests for `memory_plan_briefing`, covering truncation, missing sources, unlimited budgets, approval inclusion, trace inclusion/fallback, failure summaries, summary-mode behavior, and trace emission.
- **Docs** — documented the new tool in `HUMANS/docs/MCP.md`, added the context-assembly design note to `HUMANS/docs/DESIGN.md`, and finalized the Phase 8 design decisions in the harness-expansion project docs.

**Reasoning:** By Phase 7, the harness had the raw ingredients for rich execution context — structured phase payloads, failure history, approval state, and traces — but agents still needed several sequential tool calls before they could begin work on a phase. Phase 8 closes that gap with a single-call read surface that assembles those pieces into a budget-aware briefing packet without changing plan state.

**Approved by:** user

## [2026-03-27] Phase 7: Offline evaluation framework

**Changed:** Added the Phase 7 offline evaluation layer for harness workflows.

- **`core/tools/agent_memory_mcp/eval_utils.py`** — new eval runtime with `EvalScenario`, `EvalStep`, `EvalAssertion`, `StepResult`, `AssertionResult`, and `ScenarioResult`; YAML loading/validation; direct `run_scenario()` / `run_suite()` execution; metrics aggregation; scenario selection; trace-backed historical report helpers.
- **`memory_run_eval` / `memory_eval_report`** — new MCP tools in `plan_tools.py`. `memory_run_eval` runs seeded YAML scenarios from `memory/skills/eval-scenarios/`, records compact `eval:{scenario_id}` verification spans, and is gated behind `ENGRAM_TIER2=1`. `memory_eval_report` summarizes historical eval runs and trend deltas from those trace spans.
- **Seeded scenario suite** — added `core/memory/skills/eval-scenarios/` with five scenario YAMLs and a navigator: basic plan lifecycle, verification failure + retry, trace coverage validation, tool-registry bootstrap, and approval pause/resume.
- **Tests and docs** — expanded eval-focused test coverage to execute the seeded suite directly, documented both MCP tools in `HUMANS/docs/MCP.md`, and indexed the scenario suite from `core/memory/skills/SUMMARY.md`.

**Reasoning:** Phase 3 provided traces, but Engram still lacked a declarative way to define expected workflows, execute them against isolated fixtures, and compare results over time. The Phase 7 eval framework closes that gap with a reusable scenario format, an execution/runtime surface, a minimal reporting loop, and seeded coverage for the core harness behaviors that previous phases introduced.

**Approved by:** user

## [2026-03-26] Phase 5: Structured HITL (ApprovalDocument, memory_request_approval, memory_resolve_approval, paused plan status)

**Changed:** Operationalized `requires_approval` as a full interrupt/resume workflow:

- **`ApprovalDocument` dataclass** — YAML schema with `plan_id`, `phase_id`, `project_id`, `status` (pending/approved/rejected/expired), `requested`, `expires`, `context` (phase_title, phase_summary, sources, changes, change_class, budget_status), `resolution`, `reviewer`, `resolved_at`, `comment`. Stored at `memory/working/approvals/pending/{plan_id}--{phase_id}.yaml` while pending, moved to `resolved/` on resolution.
- **`memory_request_approval` MCP tool** — creates pending approval document and pauses plan. Auto-deduplicates: returns existing document if pending approval already exists.
- **`memory_resolve_approval` MCP tool** — resolves pending approval (approve/reject), moves document to `resolved/`, sets plan status to `active` or `blocked`. Regenerates SUMMARY.md after every operation.
- **`paused` plan status** — added to `PLAN_STATUSES`. Expresses "waiting for human input" (vs. `blocked` = technical dependency). Transitions: `active → paused` (approval requested), `paused → active` (approved), `paused → blocked` (rejected or expired).
- **Auto-pause on `requires_approval` phases** — `memory_plan_execute` start action automatically creates an approval document and pauses the plan when it encounters a `requires_approval: true` phase with no existing approval. Handles all approval states: pending (return awaiting), approved (proceed), rejected/expired (block).
- **Paused plan guard** — `memory_plan_execute` start and complete actions return an error when `plan.status == "paused"`.
- **Lazy expiry** — `load_approval()` checks `expires` on every read; if past, status transitions to `expired`, file moves to `resolved/`. Default expiry window: 7 days.
- **`working/approvals/` directory** — `pending/.gitkeep`, `resolved/.gitkeep`, and `SUMMARY.md` (approval queue navigator, regenerated after every operation).
- **`HUMANS/views/approvals.html`** — browser UI with pending approvals list (expiry countdowns, phase context, approve/reject buttons with comment field), resolved history, and expired alerts. Writes resolution YAML via File System Access API; no server required.
- **38 new tests** (190 total) — `TestApprovalDocumentDataclass` (14), `TestApprovalStorage` (8), `TestApprovalExpiry` (6), `TestApprovalsSummaryRegeneration` (3), `TestPlanPauseStatus` (5).
- **Documentation** — DESIGN.md and MCP.md updated with approval lifecycle, tool parameters, and plan status transitions.

**Reasoning:** The harness report identified the missing "workflow" layer: `requires_approval` existed as a flag but provided no structured mechanism to create, track, or resolve approval requests. This phase closes the loop — the agent can now create a serialized approval document, pause, and resume with full human oversight at decisional phase boundaries.

**Approved by:** user

## [2026-03-26] Phase 4: External tool registry (ToolDefinition, memory_register_tool, memory_get_tool_policy)

**Changed:** Added a policy storage layer for external tools so agents and orchestrators can query tool constraints before invoking them:

- **`core/memory/skills/tool-registry/`** — new directory with YAML registry files grouped by provider (`shell.yaml`, `api.yaml`, `mcp-external.yaml`). Each entry captures `name` (slug), `description`, `approval_required`, `cost_tier` (free/low/medium/high), `timeout_seconds`, optional `rate_limit`, `tags`, `schema`, and `notes`.
- **`ToolDefinition` dataclass** — added to `plan_utils.py` with full field validation (slug names, valid cost tiers, timeout ≥ 1, non-empty description/provider, dict schema). `load_registry()`, `save_registry()`, `_all_registry_tools()`, and `regenerate_registry_summary()` helpers handle YAML round-trips.
- **`memory_register_tool`** — new MCP tool; creates a new definition or replaces an existing one (no duplicates). Regenerates SUMMARY.md on every call.
- **`memory_get_tool_policy`** — new MCP tool; queries by tool_name, provider, tags (any-match), or cost_tier. Returns matching definitions with count. At least one filter required; empty results are not errors.
- **`phase_payload()` integration** — now includes a `tool_policies` field that auto-resolves registry entries matching `test`-type postcondition targets. Matching is best-effort (command-prefix slug normalization); unregistered tools yield an empty list.
- **Seed data** — `shell.yaml` ships with `pre-commit-run` (60s), `pytest-run` (120s), and `ruff-check` (30s) definitions, all free-tier and immediately useful for plan policy integration.
- **Tests** — 29 new tests (152 total); ruff clean.

**Reasoning:** The harness report identified the lack of tool policy metadata as a gap preventing the harness from advising agents on tool constraints. Engram knows about memory tools but nothing about the external tools agents actually invoke (shell commands, APIs). This phase closes that gap without adding execution — policy storage only. Phase 5 (HITL) can now use `approval_required` from registered tools in its approval-workflow design.

**Approved by:** user

## [2026-03-26] Phase 3: Structured observability (TRACES.jsonl, trace recording, query, viewer)

**Changed:** Added structured trace recording across the MCP server, enabling session-level observability:

- **TRACES.jsonl schema** — per-session trace files stored at `memory/activity/YYYY/MM/DD/chat-NNN.traces.jsonl`. Each line is a JSON span with: `span_id` (12-char UUID4 hex), `session_id`, `timestamp` (ISO 8601 with ms), `span_type` (tool_call, plan_action, retrieval, verification, guardrail_check), `name`, `status` (ok, error, denied), optional `duration_ms`, `metadata` (sanitized), and `cost`.
- **`memory_record_trace`** — new MCP tool for agent-initiated trace spans. Non-blocking; errors are caught and silently swallowed.
- **`memory_query_traces`** — new MCP tool for querying spans across sessions or date ranges. Filters by session_id, date, span_type, plan_id (in metadata), and status. Returns spans newest-first with aggregates (total_duration_ms, by_type, by_status, error_rate).
- **Internal instrumentation** — plan_create, plan_execute (start/complete/record_failure), and plan_verify all emit `plan_action` or `verification` spans automatically.
- **Metadata sanitization** — strings >200 chars truncated, credential-like field names redacted, objects >2 levels deep stringified, total metadata capped at 2 KB.
- **ACCESS.jsonl extension** — retrieval entries now include `event_type: "retrieval"`; `parse_co_access` filters by this field.
- **Session summary enrichment** — summaries include a `metrics:` frontmatter block when TRACES.jsonl exists.
- **Trace viewer UI** — `HUMANS/views/traces.html` with session selector, timeline view, filter chips, and stats bar.
- **25 new tests** covering all new functionality.

**Reasoning:** The harness expansion analysis identified observability as the biggest operational gap. This phase adds structured, queryable evidence of what happened in a session.

**Approved by:** user

## [2026-03-27] Phase 2: Inline verification, failure recording, and retry context

**Changed:** Extended the plan execution system with three new capabilities:

- **`memory_plan_verify`** — new MCP tool that evaluates a phase's postconditions without modifying plan state. Four validator types: `check` (file existence), `grep` (pattern::path regex search), `test` (allowlisted shell command with ENGRAM_TIER2 gate, metacharacter rejection, and 30s timeout), and `manual` (always skipped by automation).
- **`verify=true` on `memory_plan_execute` complete** — when set, evaluates postconditions before completing the phase. If any postcondition fails, the phase stays `in-progress` and `verification_results` are returned for diagnosis.
- **`PhaseFailure` dataclass and `record_failure` action** — phases can now accumulate a failure log. Each failure records a timestamp, reason, optional verification results, and attempt number. Failure history is surfaced in `phase_payload()` (as `failures` list and `attempt_number`) and `next_action()` (as `has_prior_failures`, `attempt_number`, and `suggest_revision` when attempts ≥ 3).
- **29 new tests** covering all four validator types, PhaseFailure serialization/round-trip/backward-compat, retry context in phase_payload and next_action, and suggest_revision threshold.

Security measures: test-type commands are allowlisted (pytest, ruff, pre-commit, mypy prefixes only), shell metacharacters are rejected, proxy environment variables are stripped, and command output is truncated to 2000 characters.

**Reasoning:** The plan system could track phases and tasks but had no way to verify that work actually met its postconditions, record failures for diagnostic context, or signal when a phase should be revised rather than retried. This closes the feedback loop between plan execution and plan governance.

**Approved by:** agent (pending review)

## [2026-03-26] Plan schema extensions: sources, postconditions, approval gates, budget

**Changed:** Extended the plan schema with four new structural features and updated the MCP tool surface to expose them:

- **`SourceSpec`** — new dataclass on `PlanPhase.sources`. Each source has `path`, `type` (`internal`/`external`/`mcp`), `intent`, and optional `uri`. Internal sources are validated for existence at save time. The `next_action()` and `phase_payload()` responses include sources so agents know what to read before acting.
- **`PostconditionSpec`** — new dataclass on `PlanPhase.postconditions`. Each postcondition has a free-text `description` and optional typed validator (`check`/`grep`/`test`/`manual` with a `target`). Bare strings coerce to `manual` type. Postconditions are surfaced in `inspect` and `start` responses.
- **`requires_approval`** — boolean flag on `PlanPhase` (default `False`). When true, the `start` action returns `approval_required: true` and `requires_approval: true` in `resulting_state`, signalling the agent to pause before writing.
- **`PlanBudget`** — new top-level dataclass on `PlanDocument.budget`. Fields: `deadline` (YYYY-MM-DD), `max_sessions` (int ≥ 1), `advisory` (bool, default `True`). Advisory budgets emit warnings; enforced budgets raise errors when exhausted. `sessions_used` is incremented by each `complete` action and persisted in the plan YAML. `budget_status()` returns `days_remaining`, `sessions_remaining`, `over_budget`, and related fields.
- **`next_action()`** now returns a structured dict (`id`, `title`, `sources`, `postconditions`, `requires_approval`) instead of a plain string.
- **`memory_plan_create`** accepts a `budget` parameter and phase dicts with all new fields.
- **`memory_plan_execute`**: `inspect` includes full new fields in the phase payload; `start` surfaces sources, postconditions, approval gate, and budget status; `complete` increments `sessions_used` and emits budget warnings.

All changes are backward-compatible: plans created before this revision load without modification and default all new fields to empty/false/null.

**Reasoning:** The original plan schema could store phases and tasks but gave agents no structured cue for what to read before acting, what must be true after, when to pause for human input, or when a project budget was exceeded. This left the agent harness incomplete — plans were passive records rather than active execution surfaces. These extensions close that gap by making plans the primary source of per-phase pre-work directives and approval constraints.

**Approved by:** agent (pending review)

## [2026-03-24] Split INTEGRATIONS.md into WORKTREE.md + INTEGRATIONS.md

**Changed:** Split `HUMANS/docs/INTEGRATIONS.md` into two focused documents:
- **WORKTREE.md** (new): Contains all worktree-mode content — integration modes (standalone, worktree, embedded MCP), quick start, CI/CD exemptions (GitHub Actions, GitLab CI, Bitbucket Pipelines), branch protection, tooling-bleed prevention (ESLint, Prettier, Ruff, TypeScript, VS Code, JetBrains, ripgrep), MCP client wiring, operational guidance, and the minimal checklist.
- **INTEGRATIONS.md** (rewritten): Now focused exclusively on third-party tool integrations — vector search, knowledge graphs, observability, orchestration, multi-agent frameworks, RAG frameworks, developer tools, recommended starting points, and the general wiring pattern.

Updated cross-references in 6 files: README.md (header links + structure tree), QUICKSTART.md (2 references split to WORKTREE.md + new INTEGRATIONS.md link), MCP.md (2 references updated), CORE.md (split into WORKTREE.md + INTEGRATIONS.md links), HELP.md (split into two table rows), docs.html (added WORKTREE.md entry with tree icon).

**Reasoning:** INTEGRATIONS.md was doing double duty — half worktree deployment operations, half third-party ecosystem tools. These serve different audiences at different times: someone deploying a worktree reads the CI/tooling sections once during setup, while someone evaluating complementary tools reads the integration sketches during planning. Splitting them makes both documents easier to navigate and avoids burying the third-party content below 250 lines of CI YAML.

**Approved by:** agent (pending review)

## [2026-03-24] README.md rewrite

**Changed:** Rewrote `README.md` to align with the current system state and the recently rewritten documentation suite. Key changes:
- Added links to MCP.md and HELP.md in the human-facing quick-reference header (previously only linked QUICKSTART, CORE, DESIGN).
- Added a **Session types** table listing all 7 session types with token budgets, replacing the inline budget table that was buried in "Bootstrap sequence".
- Added a **Bootstrap configuration** section explaining `agent-bootstrap.toml` and platform adapter files.
- Added a full **MCP server** section with installation, running, tool surface overview (51+ tools, 3 tiers, 4 resources, 4 prompts, 3 profiles), and environment variables. Previously the MCP server was only mentioned in passing.
- Expanded **How to propose changes** with the provenance trust-level table (source → initial trust → promotion path) that was previously only in `update-guidelines.md`.
- Updated the **Repository structure** tree: added `pyproject.toml`, replaced vague `tools/` entry with `agent_memory_mcp/` substructure, added all 7 browser views, added `INTEGRATIONS.md` and `HELP.md` to docs listing, added `agent-memory-capabilities.toml` to tooling, updated `working/` to reflect actual structure (USER.md and CURRENT.md at working root, not inside scratchpad).
- Removed the redundant "Bootstrap sequence" section (content absorbed into "Agent routing" and "Session types").
- Moved "Contributor tooling" and "How to orient yourself" to the end of the file (after the protocol sections agents need) to improve progressive disclosure.
- General consistency pass: governance file descriptions updated, annotation style aligned with CORE.md conventions.

**Reasoning:** The README is both the agent's architectural entry point and the repository's public-facing landing page. It needed to reflect the MCP server (completely absent before), the full session type enumeration, the provenance model, and the updated doc suite. The previous version predated the MCP.md and INTEGRATIONS.md rewrites and was missing several files from the structure tree.

**Approved by:** agent (pending review)

## [2026-03-24] Third-party integration guide added to INTEGRATIONS.md

**Changed:** Added a new "Third-party integrations" section to `HUMANS/docs/INTEGRATIONS.md` covering ecosystem tools that complement Engram. Nine subsections: semantic retrieval / vector search (LanceDB, ChromaDB, Qdrant, Turbopuffer + embedding model notes), knowledge graphs (Neo4j, FalkorDB, GraphRAG), observability and evaluation (LangFuse, LangSmith, W&B Weave), agent orchestration and scheduling (Temporal, Inngest, n8n, Activepieces), multi-agent frameworks (CrewAI, LangGraph, AutoGen), RAG and memory-augmented frameworks (LlamaIndex, Letta/MemGPT, Cognee), developer workflow tools (Aider, Raycast), recommended starting points (LanceDB+Ollama, LangFuse, Temporal, GraphRAG), and a general wiring pattern (sync layer, query layer, governance boundary).

**Reasoning:** The integrations guide previously covered only worktree deployment and tooling-bleed prevention. Users evaluating Engram alongside other AI infrastructure had no guidance on how external tools could complement the system or where the integration seams are. The new section provides concrete tool-by-tool sketches while reinforcing the governance boundary principle — external systems are read-only consumers or write back through MCP, never via direct file mutation.

**Approved by:** agent (pending review)

## [2026-03-25] Rewrite of MCP.md, QUICKSTART.md, and INTEGRATIONS.md

**Changed:** Updated three more human-facing documentation files under `HUMANS/docs/`:
- **MCP.md:** Complete rewrite. Renamed to "Engram MCP Architecture Guide". Replaced the confusing "Available MCP resources" table (which listed implementation files) with a clean "Implementation files" table. Expanded the tool inventory from an incomplete flat list (~23 Tier 0 + ~20 Tier 1) to the complete surface with one-line descriptions in tables: 32+ Tier 0 read-only tools (organized into capability introspection, file inspection, analysis, and health/governance groups), 27+ Tier 1 semantic tools (organized into plans, knowledge lifecycle, session/activity, scratchpad/skills/identity, and governance), and 7 Tier 2 raw fallback tools. Added new sections: MCP resources (4 `memory://` URIs), MCP prompts (4 workflow scaffolds), and tool profiles (`full`, `guided_write`, `read_only`). Updated the manifest section with error taxonomy and resource/prompt metadata. Consolidated the "philosophy" subsections into a tighter format. Added cross-references to HELP.md and INTEGRATIONS.md.
- **QUICKSTART.md:** Renamed to "Engram Quickstart". Added cross-reference header linking to CORE.md, MCP.md, INTEGRATIONS.md, and HELP.md. Added `docs.html` to the browser views list. Added "Attaching to an existing codebase" section pointing to INTEGRATIONS.md for worktree mode.
- **INTEGRATIONS.md:** Added cross-reference header linking to QUICKSTART.md, MCP.md, and HELP.md. Added closing reference to MCP.md at the end of the checklist.

All cross-references validated: 50+ links across the doc suite, fully connected navigation web, docs.html compatibility confirmed, no stale terminology.

**Reasoning:** MCP.md was substantially outdated — it listed ~43 tools when the server actually exposes 51+, lacked the MCP resources and prompts sections entirely, and its "Available MCP resources" section confusingly listed Python files instead of actual MCP protocol resources. QUICKSTART.md and INTEGRATIONS.md were largely current but lacked cross-references to the rest of the documentation suite, creating navigation dead ends.

**Approved by:** agent (pending review)

## [2026-03-25] Ground-up rewrite of CORE.md, DESIGN.md, and GLOSSARY.md

**Changed:** Rewrote all three human-facing documentation files under `HUMANS/docs/` to reflect the current state of the system:
- **GLOSSARY.md:** Replaced flat 20-term alphabetical list with a 6-section, ~45-term organized glossary. New sections: Architecture & Structure, Memory Lifecycle, Working Memory, Governance & Security, MCP Tool Surface. Added terms for format/runtime layer, platform adapter, agent-bootstrap.toml, browser views, scratchpad, plans, governed preview, version token, staged transaction, tool tiers, identity churn tracking, and more.
- **CORE.md:** Expanded from 8 design decisions to 12. Added decisions for MCP governed tool access (73 tools, 3 tiers), browser views (File System Access API, 7 pages), plans as first-class objects, and scratchpads bridging sessions. Updated existing decisions to reference HOME.md, agent-bootstrap.toml, session modes, token budgets, three-tier change model, and governed preview workflows. Updated "When to read which document" to include HELP.md, MCP.md, INTEGRATIONS.md.
- **DESIGN.md:** Renamed from "Agent Memory Seed" to "Engram". Updated Principles 2 (platform adapters) and 3 (progressive disclosure with browser wizard and collaborative onboarding). Added new subsections: "The governed-write model" (preview/commit, version tokens, change classes) and "Plans as durable work contexts." Added browser dashboard to use cases. Restructured Part III into "Recently Realized" (CI validation, expanded profiles, browser views, MCP health, collaborative onboarding, knowledge graph, git hooks) plus remaining future directions. Rewrote Part IV MCP section from a 5-function sketch to the actual 73-tool, three-tier surface.

All cross-references validated: 18 links across the three files, all resolving correctly. docs.html viewer compatibility confirmed (filename-based, content-agnostic). No stale "Agent Memory Seed" terminology remaining.

**Reasoning:** The three docs were written when the system was a template-stage seed project. They predated the MCP server (73 tools), browser views (7 pages), plan system, collaborative onboarding, governed-write model, and agent-bootstrap.toml. Users reading these files were getting a picture of a system that no longer existed. The rewrite brings them into alignment with the actual system architecture.

**Approved by:** agent (pending review)

## [2026-03-24] Markdown section-link support in browser views

**Changed:** Expanded the shared browser markdown renderer in `HUMANS/views/engram-utils.js` to generate stable heading IDs, support same-document section links like `#heading`, and preserve cross-document anchors like `other.md#heading` through the internal cross-reference callback. Updated `knowledge.html` and `docs.html` so cross-reference navigation can open a target document and scroll to the requested section. Updated `graph.js` and its JS tests so file-level reference extraction accepts `.md#section` links without dropping the underlying document edge.

**Reasoning:** The shared renderer only recognized bare `.md` document links. As soon as a markdown link included a fragment, the renderer either treated it as a generic external URL or left it inert, which meant section links inside docs and knowledge files could not be followed. Adding anchor-aware parsing at the shared utility layer fixes the behavior consistently across the browser views and keeps the graph/reference tooling aligned with the new link format.

**Approved by:** agent (pending review)

## [2026-03-24] Shared markdown renderer and views consolidation

**Changed:** Extracted the markdown renderer from knowledge.html into a shared `Engram.renderMarkdown()` function in `engram-utils.js`. The shared renderer is DOM-safe (no innerHTML), supports headings, bold, italic, inline code, links, fenced code blocks, tables, nested lists, blockquotes, horizontal rules, and KaTeX math (display blocks and inline). It accepts an optional `onXrefClick` callback for cross-reference navigation. Replaced the 4 separate markdown renderers (knowledge.html, projects.html, skills.html, users.html) with calls to the shared version. Eliminated the unsafe innerHTML-based regex renderers in skills.html and users.html. Added KaTeX CDN (v0.16.21 with SRI integrity) to all HTML `<head>` sections (previously only knowledge.html). Moved `.math-display` CSS to `engram-shared.css`. Updated HUMANS/README.md to document skills.html, users.html, graph overlay, and KaTeX. Updated QUICKSTART.md to list all five browser views.

**Reasoning:** The four independent markdown renderers had diverged in quality and feature coverage — knowledge.html had full math support and DOM-safe construction, projects.html lacked math, and skills/users.html used regex+innerHTML which is an XSS risk even with escapeHtml pre-processing. Consolidating to a single shared renderer ensures consistent rendering quality, eliminates the innerHTML security concern for markdown content, and enables KaTeX math rendering across all views.

**Approved by:** agent (pending review)

## [2026-03-23] Views styling polish, design tokens, and documentation

**Changed:** Introduced CSS custom properties (`:root` design tokens) in `engram-shared.css` for the full color palette, border radii, shadow tokens, and monospace font stack — replacing ~60 hardcoded hex values scattered across four HTML files. Added subtle box-shadows to all card/panel components (`--shadow-card` resting, `--shadow-hover` on interactive lift). Fixed inconsistent inline-code styling: removed the pink `color: #e11d48` in knowledge.html, unified code background to `--color-code-bg` across all pages, added shared `code` rule with monospace font stack. Added 🧠 SVG favicon to all four HTML pages. Added "View all →" link to the Knowledge Base panel header in dashboard.html (was missing — projects panel already had one). Expanded `HUMANS/README.md` from a 2-line stub to a full file inventory, architecture overview, and navigation diagram for the views. Updated `HUMANS/docs/QUICKSTART.md` to mention knowledge and project viewers.

**Reasoning:** The four viewer pages had diverged in styling conventions — hardcoded colors, inconsistent code block treatment (knowledge used pink text, projects used a different background, dashboard had yet another), and no shared shadow/depth system. CSS custom properties establish a single source of truth that makes future theming (e.g. dark mode) trivial. The documentation gap meant neither humans nor agents knew the views existed or how they related to each other.

**Approved by:** agent (pending review)

## [2026-03-23] Projects dashboard and knowledge cross-reference navigation

**Changed:** Added `HUMANS/views/projects.html` — standalone project viewer with card-based list and full detail view (metadata bar, focus callout, collapsible question cards, YAML plan timeline with phase indicators, inline notes viewer). Added click-through navigation from the dashboard projects panel to projects.html. Added cross-reference navigation to knowledge.html: clickable `related:` frontmatter entries, inline markdown links to other knowledge files, and backtick file references. Updated dashboard.html with "View all →" link in the projects panel header and clickable project rows.

**Reasoning:** The dashboard provided a summary of projects and knowledge but no way to drill into detail. The projects viewer enables browsing the full project tree (questions, plans, notes) without needing an agent session. Cross-reference navigation in the knowledge viewer surfaces connections between knowledge files that were previously invisible to users.

**Approved by:** agent (pending review)

## [2026-03-23] Browser dashboard for memory repo

**Changed:** Added `HUMANS/views/dashboard.html` — a read-only browser-based dashboard that uses the File System Access API to display the state of a local memory repository. Panels: User Portrait, System Health (session/knowledge/skill/project counts, ACCESS entry stats, maturity stage), Active Projects, Recent Activity, Knowledge Base domain map, Scratchpad, and Skills. Also added a dashboard link to the setup wizard's output step so users discover it after onboarding.

**Reasoning:** Users had no way to get a quick visual overview of their memory system outside of an agent session. The dashboard extends the existing setup.html browser-only pattern (no server, no data leaves the machine) and reuses its design system for visual consistency.

## [2026-03-23] Onboarding skill refinements from validation

**Changed:** Applied three refinements to `core/memory/skills/onboarding.md` based on persona dry-run validation: (1) Phase A now includes a language-calibration note so agents adapt "repository" to the user's technical level; (2) Phase B pacing guidance now includes two concrete transition signals (user has a tangible artifact/decision, or agent has observed 4+ audit categories); (3) Discovery audit section now notes that categories should be interpreted for the user's domain with concrete translation examples. Also expanded the seed-task fallback list with a non-technical option ("organizing a project").

**Reasoning:** Validation across developer, researcher, and non-technical personas found the flow worked well for developers but had friction points for less technical users: jargon in the warm start, no concrete pacing heuristics for open-ended tasks, and software-centric audit categories.

**Approved by:** Alex

## [2026-03-22] Governance consolidation Phase 3 and maturity roadmap

**Changed:** Split `curation-policy.md` into three focused files: `curation-policy.md` (hygiene, decay, promotion rules), `content-boundaries.md` (trust-weighted retrieval and instruction containment), and `security-signals.md` (temporal decay, anomaly detection, drift monitoring, governance feedback, and periodic review orchestration). Added `security-signals.md` to the periodic review manifest in `INIT.md` and `agent-bootstrap.toml`; added `content-boundaries.md` to on-demand guidance in `INIT.md`. Updated cross-references across 13 files. Replaced the completed consolidation roadmap with a forward-looking `maturity-roadmap.md` tied to system maturity stages.

**Reasoning:** The original `curation-policy.md` had grown into a monolithic document covering three distinct concerns. Splitting reduces per-load token cost and improves maintainability. The consolidation roadmap's phases were all complete, so it was replaced with a maturity roadmap that maps future governance improvements to system maturity triggers (Calibration, periodic review count, MCP enforcement, Consolidation stage).

**Approved by:** Alex

## [2026-03-22] Legacy onboarding fallback and validator realignment

**Changed:** Archived the pre-redesign interview-style onboarding flow as `core/memory/skills/_archive/onboarding-v1.md` and added an archived-fallback reference in `core/memory/skills/SUMMARY.md`. Realigned the validator, session-start guidance, setup prompt-copy text, and Quickstart copy with the repo's current `core/memory/HOME.md`-based returning-session contract.

**Reasoning:** The collaborative onboarding redesign replaced the old intake flow, but the legacy procedure still needed an explicit fallback path. At the same time, the validator and setup guidance were still enforcing the older `projects/SUMMARY.md` startup contract, which had diverged from the architecture docs and machine bootstrap manifest. This restores consistency across runtime docs, tooling, and fallback onboarding behavior.

**Approved by:** Alex

## [2026-03-22] Collaborative onboarding redesign

**Changed:** Rewrote `core/memory/skills/onboarding.md` from an interview-style intake into a four-phase collaborative first-session flow centered on a seed task, inline capability demonstrations, post-hoc discovery audit, explicit profile confirmation, and the existing read-only export path. Updated `core/governance/first-run.md` and `core/memory/skills/SUMMARY.md` to describe the new onboarding behavior.

**Reasoning:** The previous flow preserved governance well but taught the wrong relationship model: the agent asked questions and the user filled out a profile. The redesign keeps the same safety invariants while improving user-friendliness through real collaboration, preserving consistency with existing export and archival mechanisms, and maintaining context efficiency by keeping the procedure in a single concise skill file.

**Approved by:** Alex

## [2026-03-22] Framework consistency review and README refactor

**Changed:** README slimmed from 434 to 268 lines — moved session reflection format to curation-policy.md, git publication model and MCP revert semantics to update-guidelines.md, compressed bootstrap sequence to routing pointers. Fixed INIT.md Automation path (`core/memory/working/HOME.md` → `core/memory/HOME.md`) and dangling arrow in Compact returning manifest. Aligned agent-bootstrap.toml with INIT.md by adding HOME.md to all session modes. Fixed HOME.md namespace list (`projects/OUT/` → `projects/`). Created missing `core/memory/working/projects/ACCESS.jsonl`. Added cross-reference comments between INIT.md and agent-bootstrap.toml.

**Reasoning:** Preparing for test users. README was doing too many jobs (architecture + detailed spec) and inflating first-run token cost. INIT.md and agent-bootstrap.toml had diverged after HOME.md was introduced, creating a split-brain loading manifest. Several path references from the recent reorganization were stale.

**Approved by:** Alex

---

## Prime Example

This is the actual first changelog entry, recorded by Claude Opus 4.6 at system creation. _Note: folder names below refer to the original directory structure, later reorganized under `core/memory/` (e.g. `identity/` → `core/memory/users/`, `chats/` → `core/memory/activity/`)._

## [2026-03-15] Initial system creation

**Changed:** Repository initialized with base template. Folders created for `identity/`, `knowledge/`, `skills/`, `chats/`, and `meta/`. Core protocols established in README.md including access-tracking via ACCESS.jsonl, progressive summary compression, bootstrap sequence, and update governance.

**Reasoning:** Starting point for a persistent, version-controlled Engram memory system. The template is intentionally minimal — it provides structure and protocols but almost no content, so that all personalization emerges from actual user interaction rather than assumptions.

**Approved by:** Alex
