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

## [2026-04-03] Terminal portability commands for export and import

**Changed:** Added `engram export` with markdown, JSON, and tar bundle formats over the stable portability roots (`core/INIT.md`, `core/governance/review-queue.md`, and `core/memory/`), plus `engram import` for previewing or applying those bundles with digest validation and explicit overwrite handling. Added focused unit coverage, subprocess integration tests, and updated the CLI guide and quickstart with backup and migration workflows.
**Reasoning:** The final CLI roadmap gap was portability: there was no shell-native way to package an Engram instance for backup, migration, or seeding another repo without reverse-engineering repository state by hand. Shipping export/import closes that gap with a shared runtime contract instead of ad hoc scripts.
**Approved by:** agent (pending review)

## [2026-04-03] Terminal lifecycle commands for promote and archive

**Changed:** Added `engram promote` and `engram archive` as governed lifecycle commands that wrap the existing semantic knowledge tools. The CLI now exposes preview and apply flows for promoting reviewed `_unverified` notes into verified knowledge and archiving stale knowledge into `memory/knowledge/_archive/`, with focused unit coverage, subprocess integration tests, and updated CLI/quickstart docs.
**Reasoning:** After shipping maintenance previews, the main missing terminal lifecycle gap was the write-side handoff from review decisions into actual governed file movement. Exposing promotion and archival through the CLI closes that gap while still reusing the existing semantic write contracts rather than reimplementing lifecycle logic.
**Approved by:** agent (pending review)

## [2026-04-03] Terminal maintenance preview commands for review and aggregation

**Changed:** Added `engram review` for shell-first maintenance candidate walkthroughs and `engram aggregate` for preview-only ACCESS aggregation reporting. Both commands reuse the existing review-queue, unverified-content, and aggregation heuristics, ship with focused unit and subprocess coverage, and are documented in the CLI guide and quickstart.
**Reasoning:** After the earlier read, write, plan, approval, trace, and diff slices, the main missing terminal maintenance surface was a safe preview layer for governance and ACCESS cleanup work. Shipping review and aggregation previews closes that gap without exposing write-side lifecycle mutations prematurely.
**Approved by:** agent (pending review)

## [2026-04-03] Git-backed memory diff surface for the terminal CLI

**Changed:** Added `engram diff` as a git-backed memory inspection command with namespace and inclusive date filters, human and JSON rendering, and annotations for frontmatter edits, trust transitions, and newly added files. Added focused unit and subprocess coverage and documented the new terminal surface in the CLI guide.
**Reasoning:** The CLI expansion roadmap still lacked a read-only way to answer "what changed?" without manually composing git commands and then translating raw file diffs back into memory concepts. A memory-aware diff surface closes that inspection gap for humans, shell-based agents, and automation.
**Approved by:** agent (pending review)

## [2026-04-02] Full Tier 1 semantic schema coverage

**Changed:** Extended the shared `memory_tool_schema` registry to cover the remaining Tier 1 semantic helpers, including `memory_analyze_graph`, `memory_list_pending_reviews`, `memory_list_plans`, `memory_plan_verify`, `memory_query_traces`, `memory_plan_briefing`, `memory_scan_drop_zone`, `memory_get_tool_policy`, `memory_semantic_search`, and `memory_reindex`. Updated the corresponding semantic-tool docstrings, aligned the existing `memory_update_user_trait` and `memory_update_skill` docstrings with the schema-backed guidance pattern, and simplified the README and MCP guide wording to describe full Tier 1 semantic coverage.
**Reasoning:** After the earlier knowledge, governance, session, access, and graph passes, the only remaining schema-discoverability gaps were helper tools whose filters, defaults, and runtime caveats still required caller guesswork. Covering the rest of Tier 1 closes that gap and makes the semantic surface uniformly introspectable without changing behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for graph curation workflows

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_prune_redundant_links`, `memory_audit_link_density`, and `memory_prune_weak_links`, including dry-run defaults, graph-scope path behavior, dense-link audit thresholds, the weak-link signal enum, and path-versus-scope precedence. Updated the corresponding graph-tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the access logging and aggregation pass, the remaining high-value graph curation surfaces still hid their real scope, threshold, and preview semantics behind plain scalar parameters. Surfacing those contracts through the shared registry reduces host guesswork without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for access logging and aggregation workflows

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_log_access`, `memory_run_aggregation`, `memory_session_flush`, and `memory_reset_session_state`, including session-id fallback behavior, controlled ACCESS fields, dry-run aggregation defaults, supported folder roots, trigger normalization, and the explicit no-argument session-state reset contract. Updated the corresponding session-tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the session continuity and plan governance pass, the remaining high-value semantic gaps were the access logging and aggregation tools whose routing, fallback, and preview semantics were not visible from their plain signatures. Surfacing those contracts through the shared registry reduces host guesswork without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for session continuity and plan governance workflows

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_checkpoint`, `memory_append_scratchpad`, `memory_record_chat_summary`, `memory_record_reflection`, `memory_plan_resume`, `memory_plan_review`, `memory_stage_external`, `memory_run_eval`, `memory_eval_report`, and `memory_resolve_review_item`, including staged-without-commit checkpointing, scratchpad target normalization, canonical session requirements, governed preview and version-token review-queue behavior, list-versus-export plan review flow, and eval environment and date-filter constraints. Updated the corresponding session and plan tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the knowledge lifecycle pass, the main remaining opaque semantic surfaces were session continuity and plan governance workflows whose stateful behavior and conditional requirements were not visible from their plain string signatures. Surfacing those contracts through the shared registry reduces host guesswork without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for knowledge lifecycle transitions

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_demote_knowledge`, `memory_archive_knowledge`, and `memory_add_knowledge_file`, including inferred destination behavior for demotion/archival, governed preview support, optimistic-lock version tokens, low-trust-only creation, canonical session ids, and optional ISO expiration dates. Updated the corresponding knowledge-tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the promotion/reorganization pass, the remaining high-value knowledge write surfaces were lifecycle transitions and unverified file creation. Their real constraints are mostly hidden behind plain string parameters, so surfacing them through the shared registry reduces host guesswork without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for preview-first knowledge workflows

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_promote_knowledge`, `memory_promote_knowledge_subtree`, `memory_reorganize_path`, and `memory_update_names_index`, including inferred target behavior, dry-run defaults, and the fixed output-path contract for generated names indexes. Updated the corresponding knowledge-tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the governance-flow pass, the main remaining opaque semantic writes were the knowledge workflows whose preview, dry-run, and path-inference behavior is not visible from outer type hints alone. Surfacing those contracts through the shared registry reduces caller guesswork without altering runtime semantics.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for protected governance workflows

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_record_periodic_review` and `memory_revert_commit`, including the stage enum, preview/apply approval-token requirement, and revert preview-token confirmation flow. Added docstrings for both tools and refreshed the README and MCP guide coverage notes.
**Reasoning:** After the earlier trace and tool-registry pass, the most important remaining opaque inputs were the protected governance tools whose write path depends on preview-time tokens and conditional arguments. Surfacing those contracts through the shared registry removes another source of host-side guesswork without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for traces and tool registry writes

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_record_trace` and `memory_register_tool`, including the canonical trace span enums, the sanitized metadata and cost payload guidance, and the protected tool-registry write fields. Updated the corresponding semantic-tool docstrings plus the README and MCP guide coverage notes.
**Reasoning:** After the earlier plan, approval, ACCESS, and frontmatter passes, the remaining caller-facing opaque inputs were concentrated in trace logging and tool-registry registration. Surfacing those contracts through the same additive schema path removes another pair of guessy dict-shaped inputs without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Plan-schema parity for failure payloads and single-file frontmatter updates

**Changed:** Moved the verification-result item schema into the shared plan-schema source so `memory_plan_schema`, `memory_tool_schema("memory_plan_create")`, and `engram-mcp plan create --json-schema` all expose the same typed failure payload shape. Extended the generic schema registry to cover `memory_update_frontmatter` in addition to the existing bulk frontmatter path, and updated the raw frontmatter tool docstring to point callers at `memory_tool_schema`.
**Reasoning:** The previous schema pass still left one stale generic object branch inside plan-create failure records and kept the single-file raw frontmatter tool off the shared introspection path. Aligning those remaining surfaces removes another source of caller guesswork without changing tool behavior.
**Approved by:** user

## [2026-04-02] Schema coverage expansion for approvals and raw batch writes

**Changed:** Extended the shared `memory_tool_schema` registry to cover `memory_request_approval` and `memory_update_frontmatter_bulk`, and replaced the opaque `memory_plan_execute.verification_results` item schema with a compatibility-preserving typed shape that documents the tool-generated result fields while still allowing legacy custom failure payloads.
**Reasoning:** The first schema-discoverability pass still left approval requests, raw frontmatter batch updates, and plan verification payloads partly opaque to MCP hosts that rely on machine-readable contracts. Expanding the shared registry keeps cross-tool callers on one introspection path and makes verification results legible without changing runtime behavior.
**Approved by:** user

## [2026-04-02] Cross-tool schema discoverability hardening

**Changed:** Added `memory_tool_schema` as a generic Tier 0 schema lookup surface backed by a shared schema registry for the audit-targeted MCP tools. Extended the registry beyond plan creation to cover `memory_plan_execute`, ACCESS-entry batch/session logging, review and approval verdict tools, and user/skill update inputs; updated the capability manifest and MCP docs to advertise the new read tool. Hardened the affected semantic-tool docstrings so they enumerate canonical enum values and conditional requirements, and changed batch ACCESS validation to aggregate multiple entry errors for `memory_log_access_batch` and the ACCESS-entry path inside `memory_record_session`.
**Reasoning:** The earlier `memory_plan_schema` work solved discoverability for plan creation only. The broader audit showed the same caller-guessing problem across other semantic tools, especially where batch input or opaque nested dicts hid enum and conditional requirements. A shared registry plus additive generic lookup keeps the machine-readable contract in one place, while aggregated ACCESS validation removes the remaining blind retry loop from the session logging surface.
**Approved by:** user

## [2026-04-02] Plan tool caller UX hardening

**Changed:** Added `memory_plan_schema` as a Tier 0 read-only introspection tool, enriched `memory_plan_create` with explicit nested-schema help text, normalized a narrow alias set for common caller guesses (`modify`, `code`, `file_check`), aggregated nested phase validation errors into one response, and made `preview=true` return structured validation feedback for invalid plan-create requests instead of raising immediately. Extended the installed `engram-mcp` CLI with a schema-backed `plan create` help path so `engram-mcp plan create --help` and `--json-schema` reuse the same contract locally. Updated the capability manifest, MCP documentation, and focused tests to keep the declared surface aligned with runtime behavior.
**Reasoning:** Plan creation had become a blind guess-and-retry loop for callers because the MCP-visible contract hid nested enums and conditional requirements while the coercion layer failed fast on the first error. This hardening makes the contract inspectable, surfaces multiple nested issues in one pass, and preserves the governed preview workflow even when the request is invalid.
**Approved by:** user

## [2026-03-29] Proxy host-specific operator examples

**Changed:** Refined `HUMANS/docs/PROXY.md` with operator-facing Claude Code and Cursor examples that show the verified `engram-proxy` launch commands, the host setting to change conceptually, smoke-test steps, and the default assumption that these hosts are home-context paths unless custom request headers are separately verified. Tightened `HUMANS/docs/QUICKSTART.md` so the lightweight setup flow points directly to those detailed examples.
**Reasoning:** The original proxy guide explained the architecture and generic setup path, but it still left too much translation work to the operator. This refinement makes the host-specific path more actionable without pretending unverified host config-file formats or custom-header capabilities are stable facts.
**Approved by:** user

## [2026-03-29] Optional proxy documentation and setup path

**Changed:** Added `HUMANS/docs/PROXY.md` as the human-facing guide for `engram-proxy`, covering per-platform setup for Claude Code and Cursor, CLI/config reference, latency expectations, troubleshooting, and the upgrade path from sidecar-only to proxy-plus-sidecar mode. Updated `HUMANS/docs/QUICKSTART.md`, `HUMANS/docs/SIDECAR.md`, and `README.md` so the proxy path is discoverable from the normal setup flow.
**Reasoning:** The proxy runtime and CLI existed, but operators still lacked a coherent setup path for actually routing supported platforms through it. Documenting the proxy closes that adoption gap while keeping the deployment model honest about limitations and fallback paths.
**Approved by:** user

## [2026-03-29] memory_checkpoint registration and docs

**Changed:** Registered `memory_checkpoint` in the capability manifest as an automatic-tier scratchpad operation, added host-facing manifest metadata for its staged-no-commit behavior, and documented the tool in `HUMANS/docs/MCP.md` with its parameters and intended relationship to scratchpad appends versus heavier mid-session syncs.
**Reasoning:** The tool itself had landed in the runtime, but the declared capability surface and human-facing MCP guide still treated it as invisible. Registering it closes the discovery gap for MCP hosts and makes the lightweight compaction-defense workflow legible to future agents and operators.
**Approved by:** user

## [2026-03-29] Claude Code sidecar observer

**Changed:** Added the `engram-sidecar` CLI as a passive session-observer workflow for Engram, backed by Claude Code transcript parsing, governed ACCESS/session writes through stdio `engram-mcp`, and persistent local replay state for stable `chat-NNN` allocation across reruns. Added human-facing documentation for the sidecar in `HUMANS/docs/SIDECAR.md`, linked it from `HUMANS/docs/QUICKSTART.md`, and updated `README.md` to surface the new CLI and repository structure.
**Reasoning:** Engram needed a low-friction way to bootstrap ACCESS data and session records from real transcript evidence without changing the live runtime or relying on perfect agent self-report. Shipping the observer as an optional standalone CLI keeps the automation conservative, portable, and compatible with existing MCP-host workflows.
**Approved by:** user

## [2026-03-28] Bootstrap routing to project context injector

**Changed:** Normalized `memory_session_bootstrap` active-plan entries to use the same compact `next_action` shape now exposed by `memory_context_project`, and added a structured `resume_context` hint that points hosts directly to `memory_context_project(project=...)` for each active plan. The session-bootstrap recommendations now name the concrete context-injector call for the leading active plan instead of a generic resume reminder. Expanded bootstrap test coverage to lock the new active-plan payload and recommendation text.

**Reasoning:** The new project-context metadata was useful, but a host starting from the returning-agent bootstrap path still had to infer which tool to call next and reconcile a different `next_action` shape. Aligning the bootstrap bundle with the project-context contract removes that translation step and makes the resume path explicit.

**Approved by:** user

## [2026-03-28] Context injector payload tuning

**Changed:** Refined `memory_context_project` so `include_user_profile` now defaults to an automatic mode: when a validated or raw-fallback plan is present, the injector omits the user profile unless the caller explicitly requests it; when no plan is present, the user profile is still included by default. Added a compact `next_action` object to project-context metadata so hosts can read the next step without parsing the rendered plan body. Expanded project-context integration coverage for auto profile omission, explicit overrides, compact next-action metadata, and the no-actionable-phase case.

**Reasoning:** Live probing showed the default project payload was still heavier than necessary once a plan had already been selected, and hosts still had to parse the body to find the next task. This refinement makes the default payload leaner while exposing the highest-value action signal directly in metadata.

**Approved by:** user

## [2026-03-28] Context injectors for home and project startup

**Changed:** Added `memory_context_home` and `memory_context_project` as Tier 0 read-only MCP tools, backed by a new `read_tools/_context.py` module with shared context-assembly helpers (`_read_file_content`, `_read_section_with_budget`, `_build_budget_report`, `_is_placeholder`, `_assemble_markdown_response`). The tools now return Markdown with a JSON metadata header that includes `format_version` and `body_sections`, and each body section carries an explicit provenance line plus section comment markers for easier host-side parsing. `memory_context_project` also falls back to a raw-YAML summary when a draft plan cannot pass the stricter plan-schema loader yet, so project context still includes purpose, current phase, and sources during active planning. Both tools apply soft character budgets without truncating mid-file and surface included/dropped sections via `budget_report`. Registered the tools in the read-tool package, added focused helper and integration tests, updated the capability manifest, documented the new context-injector family in `HUMANS/docs/MCP.md`, and added bootstrap guidance in `README.md`.

**Reasoning:** Engram's existing bootstrap path required agents to understand the file-based routing protocol and manually budget several sequential reads. The new context injectors reduce that to a single read-only MCP call for the two most common session patterns while preserving provenance, graceful degradation, and token efficiency.

**Approved by:** user

## [2026-03-27] Git reliability hardening (Phase 15)

**Changed:** Enhanced `git_repo.py` with retry resilience and diagnostics. Added `_is_transient_failure()` for classifying lock contention and I/O errors. `commit()` now retries up to 3 times with exponential backoff (0.5s, 1s, 2s) on transient failures. Added `_try_cleanup_stale_index_lock()` and `_try_cleanup_all_stale_locks()` alongside existing HEAD.lock cleanup. All lock cleanups now log warnings. Added `health_check()` method returning structured diagnostics (lock files, repo validity, HEAD state, index state, filesystem writability). Added `memory_git_health` MCP tool (Tier 0, read-only). 14 new tests in `test_git_reliability.py`. Resolved review queue item 2026-03-26-review-core-tools-agent-memory-mcp-git-repo-py.

**Reasoning:** Git reliability is foundational — every write goes through git_repo.py. FUSE-mounted filesystems can leave orphaned lock files that block all commits. Retry with backoff and stale lock cleanup make git operations resilient to transient failures without manual intervention.

**Approved by:** user

## [2026-03-27] Trace enrichment (Phase 14)

**Changed:** Added `estimate_cost()` helper to `plan_utils.py` for character-to-token cost estimation (4 chars/token default). Plan execution traces (start, complete, record_failure) now include `cost: {tokens_in, tokens_out}`. `memory_query_traces` aggregates now include `total_cost` with summed token counts. `record_trace()` return value (`span_id`) supports parent-child span chaining via `parent_span_id`. 8 new tests in `TestTraceEnrichment`. Updated DESIGN.md.

**Reasoning:** Phase 3 traces had empty cost fields and unused parent-child relationships. The deep research report recommends end-to-end traces with latency/cost as critical operational metrics. Cost estimation and span hierarchy make the observability layer production-ready for periodic reviews.

**Approved by:** user

## [2026-03-27] Eval hardening (Phase 13)

**Changed:** Added isolated eval execution (`run_scenario(isolated=True)`), pytest CI runner (`test_eval_scenarios.py` with `@pytest.mark.eval`), result history tracking (`append_eval_history`, `load_eval_history` with `eval-history.jsonl`), and regression detection (`compare_eval_runs()` with 10% threshold). Created 4 new eval scenarios for Phases 10-12: run state checkpoint/resume, run state failure recovery, guard pipeline blocking, and policy enforcement. Updated seed scenario tests. Updated DESIGN.md.

**Reasoning:** The eval framework (Phase 7) executed scenarios directly with no isolation, CI integration, or regression detection. The deep research report stresses that "eval value compounds over the lifecycle." Hardening makes evals reliable enough for CI pipelines and enables catching regressions between runs.

**Approved by:** user

## [2026-03-27] Runtime guard pipeline (Phase 12)

**Changed:** Added `guard_pipeline.py` module with `Guard` abstract base class, `GuardPipeline`, `GuardContext`, `GuardResult`, and `PipelineResult`. Four built-in guards: `PathGuard` (wraps existing path_policy.py), `ContentSizeGuard` (100 KB default, configurable via `ENGRAM_MAX_FILE_SIZE`), `FrontmatterGuard` (validates source/trust enums), `TrustBoundaryGuard` (requires approval for agent-assigned trust:high). Pipeline short-circuits on block, accumulates warnings, emits `guardrail_check` trace spans. `default_pipeline()` convenience constructor. 28 tests in `test_guard_pipeline.py`. Updated DESIGN.md.

**Reasoning:** Guardrails were limited to path_policy.py and prose governance docs. The deep research report recommends guardrails as a parallel control plane with structured validation. The guard pipeline centralizes validation into an extensible, observable system that new guards can plug into without modifying write paths.

**Approved by:** user

## [2026-03-27] Tool policy enforcement (Phase 11)

**Changed:** Made tool registry policies enforceable at runtime. Added `PolicyCheckResult` dataclass and `check_tool_policy()` function to `plan_utils.py` with approval gating, rate limit enforcement (sliding window from trace spans), cost tier awareness, and eval bypass. Added `policy_violation` to `TRACE_SPAN_TYPES`. Wired policy checks into `verify_postconditions()` for test-type postconditions with automatic trace emission on violations. Rate limit parsing supports `N/minute`, `N/hour`, `N/day`, and `N/session` formats. 14 new tests in `TestToolPolicyEnforcement`. Updated DESIGN.md and MCP.md.

**Reasoning:** The tool registry (Phase 4) stored approval, cost, and rate limit metadata as informational fields with no runtime enforcement. The deep research report recommends a tool policy layer that can block or require approval based on context. This phase closes the gap between declared policy and enforced policy.

**Approved by:** user

## [2026-03-27] Run state layer (Phase 10)

**Changed:** Added a formal RunState JSON schema and persistence layer for plan execution. New `RunState`, `RunStatePhase`, and `RunStateError` dataclasses in `plan_utils.py` with `save_run_state()`, `load_run_state()`, `update_run_state()`, `validate_run_state_against_plan()`, `check_run_state_staleness()`, and `prune_run_state()` helpers. Wired auto-save into `memory_plan_execute` (start, complete, record_failure). Integrated run state into `assemble_briefing()` output. Added new `memory_plan_resume` MCP tool for single-call plan resumption with run state context. 33 new tests in `TestRunState`. Updated DESIGN.md and MCP.md.

**Reasoning:** Plan execution state was distributed across plan YAML files, git commits, and operations.jsonl, requiring agents to re-derive progress on resumption. The deep research report's strongest recommendation is to separate "correctness state" (run state) from "recall memory" to prevent state drift. RunState provides explicit checkpoints with intermediate outputs, task position, and resumption hints, making multi-session plan execution reliable and context-efficient.

**Approved by:** user

## [2026-03-28] Retrieval discipline directive

**Changed:** Added a "Retrieval discipline" paragraph to `core/INIT.md` and a `[behavioral_directives]` section to `agent-bootstrap.toml` requiring agents to search memory before answering recall-type questions.

**Reasoning:** Agents occasionally confabulate or rely on stale loaded context when asked about prior conversations or stored knowledge. Making "search before answering" an explicit protocol closes this gap, mirroring the retrieval-first pattern observed in OpenClaw's architecture.

**Approved by:** user

## [2026-03-28] Pre-compaction flush protocol

**Changed:** Added a "Context-pressure flush" section to `core/memory/skills/session-sync.md`, a cross-reference in `core/governance/session-checklists.md`, and a `[compaction_flush]` section in `agent-bootstrap.toml`. The protocol auto-triggers a mid-session checkpoint when >75% of the context window is consumed or when the platform signals an impending compaction.

**Reasoning:** Context compaction can silently discard uncommitted working state. By making pre-compaction flush an explicit, triggerable protocol, in-progress notes, decisions, and scratchpad content are preserved before the context window resets.

**Approved by:** user

## [2026-03-28] Freshness-weighted search ranking

**Changed:** Created `core/tools/agent_memory_mcp/freshness.py` (shared utility with `parse_date`, `effective_date`, `freshness_score` using exponential decay, 180-day half-life). Modified `memory_search` in `read_tools.py` to accept an optional `freshness_weight` parameter (0.0–1.0, default 0.0) that re-ranks results by a combined text-match + temporal-decay score. Added 19 new tests in `test_search_freshness.py`. Documented the parameter in `agent-memory-capabilities.toml`.

**Reasoning:** Pure text-match search returns results in file-system order with no recency signal. Adding optional freshness weighting lets agents prefer recently verified knowledge when relevance is otherwise equal, improving retrieval quality for evolving topics.

**Approved by:** user

## [2026-03-28] Semantic search with hybrid ranking

**Changed:**

- **`core/tools/agent_memory_mcp/tools/semantic/search_tools.py`** — new module implementing `EmbeddingIndex` class (SQLite-backed, incremental, `all-MiniLM-L6-v2` embeddings), `_BM25` scorer, and ACCESS.jsonl helpfulness loader. Exposes two MCP tools: `memory_semantic_search` (hybrid vector + BM25 + freshness + helpfulness ranking with configurable weights) and `memory_reindex` (force rebuild).
- **`core/tools/agent_memory_mcp/tools/semantic/__init__.py`** — registered `search_tools` in the semantic package.
- **`pyproject.toml`** — added `[search]` optional dependency group (`sentence-transformers>=2.6`, `numpy>=1.24`).
- **`.gitignore`** — added `.engram/` for the embedding index cache.
- **`HUMANS/tooling/agent-memory-capabilities.toml`** — added `memory_semantic_search` and `memory_reindex` to `semantic_extensions` tool set.
- **`HUMANS/docs/MCP.md`** — added "Semantic search (optional)" section documenting both tools, hybrid scoring formula, and setup.
- **`HUMANS/docs/DESIGN.md`** — moved "Semantic retrieval" from medium-term to "recently realized".
- **`core/INIT.md`** — added preference note for `memory_semantic_search` when available.
- **`core/tools/tests/test_semantic_search.py`** — 32 tests covering tokenization, BM25 scoring, file chunking, helpfulness loading, index database operations, embedding integration (skipped when deps not installed), MCP tool integration, and graceful degradation.

**Reasoning:** Semantic (vector-based) search dramatically improves retrieval precision for natural language queries over growing knowledge bases. The hybrid scoring model (40% vector + 30% BM25 + 15% freshness + 15% helpfulness) leverages Engram's unique ACCESS.jsonl data as a reranking signal — something no other memory system offers. The local-only embedding model respects Engram's local-first principle.

**Approved by:** user

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

**Approved by:** user (batch-reviewed 2026-03-27)

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

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-24] Split INTEGRATIONS.md into WORKTREE.md + INTEGRATIONS.md

**Changed:** Split `HUMANS/docs/INTEGRATIONS.md` into two focused documents:
- **WORKTREE.md** (new): Contains all worktree-mode content — integration modes (standalone, worktree, embedded MCP), quick start, CI/CD exemptions (GitHub Actions, GitLab CI, Bitbucket Pipelines), branch protection, tooling-bleed prevention (ESLint, Prettier, Ruff, TypeScript, VS Code, JetBrains, ripgrep), MCP client wiring, operational guidance, and the minimal checklist.
- **INTEGRATIONS.md** (rewritten): Now focused exclusively on third-party tool integrations — vector search, knowledge graphs, observability, orchestration, multi-agent frameworks, RAG frameworks, developer tools, recommended starting points, and the general wiring pattern.

Updated cross-references in 6 files: README.md (header links + structure tree), QUICKSTART.md (2 references split to WORKTREE.md + new INTEGRATIONS.md link), MCP.md (2 references updated), CORE.md (split into WORKTREE.md + INTEGRATIONS.md links), HELP.md (split into two table rows), docs.html (added WORKTREE.md entry with tree icon).

**Reasoning:** INTEGRATIONS.md was doing double duty — half worktree deployment operations, half third-party ecosystem tools. These serve different audiences at different times: someone deploying a worktree reads the CI/tooling sections once during setup, while someone evaluating complementary tools reads the integration sketches during planning. Splitting them makes both documents easier to navigate and avoids burying the third-party content below 250 lines of CI YAML.

**Approved by:** user (batch-reviewed 2026-03-27)

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

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-24] Third-party integration guide added to INTEGRATIONS.md

**Changed:** Added a new "Third-party integrations" section to `HUMANS/docs/INTEGRATIONS.md` covering ecosystem tools that complement Engram. Nine subsections: semantic retrieval / vector search (LanceDB, ChromaDB, Qdrant, Turbopuffer + embedding model notes), knowledge graphs (Neo4j, FalkorDB, GraphRAG), observability and evaluation (LangFuse, LangSmith, W&B Weave), agent orchestration and scheduling (Temporal, Inngest, n8n, Activepieces), multi-agent frameworks (CrewAI, LangGraph, AutoGen), RAG and memory-augmented frameworks (LlamaIndex, Letta/MemGPT, Cognee), developer workflow tools (Aider, Raycast), recommended starting points (LanceDB+Ollama, LangFuse, Temporal, GraphRAG), and a general wiring pattern (sync layer, query layer, governance boundary).

**Reasoning:** The integrations guide previously covered only worktree deployment and tooling-bleed prevention. Users evaluating Engram alongside other AI infrastructure had no guidance on how external tools could complement the system or where the integration seams are. The new section provides concrete tool-by-tool sketches while reinforcing the governance boundary principle — external systems are read-only consumers or write back through MCP, never via direct file mutation.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-25] Rewrite of MCP.md, QUICKSTART.md, and INTEGRATIONS.md

**Changed:** Updated three more human-facing documentation files under `HUMANS/docs/`:
- **MCP.md:** Complete rewrite. Renamed to "Engram MCP Architecture Guide". Replaced the confusing "Available MCP resources" table (which listed implementation files) with a clean "Implementation files" table. Expanded the tool inventory from an incomplete flat list (~23 Tier 0 + ~20 Tier 1) to the complete surface with one-line descriptions in tables: 32+ Tier 0 read-only tools (organized into capability introspection, file inspection, analysis, and health/governance groups), 27+ Tier 1 semantic tools (organized into plans, knowledge lifecycle, session/activity, scratchpad/skills/identity, and governance), and 7 Tier 2 raw fallback tools. Added new sections: MCP resources (4 `memory://` URIs), MCP prompts (4 workflow scaffolds), and tool profiles (`full`, `guided_write`, `read_only`). Updated the manifest section with error taxonomy and resource/prompt metadata. Consolidated the "philosophy" subsections into a tighter format. Added cross-references to HELP.md and INTEGRATIONS.md.
- **QUICKSTART.md:** Renamed to "Engram Quickstart". Added cross-reference header linking to CORE.md, MCP.md, INTEGRATIONS.md, and HELP.md. Added `docs.html` to the browser views list. Added "Attaching to an existing codebase" section pointing to INTEGRATIONS.md for worktree mode.
- **INTEGRATIONS.md:** Added cross-reference header linking to QUICKSTART.md, MCP.md, and HELP.md. Added closing reference to MCP.md at the end of the checklist.

All cross-references validated: 50+ links across the doc suite, fully connected navigation web, docs.html compatibility confirmed, no stale terminology.

**Reasoning:** MCP.md was substantially outdated — it listed ~43 tools when the server actually exposes 51+, lacked the MCP resources and prompts sections entirely, and its "Available MCP resources" section confusingly listed Python files instead of actual MCP protocol resources. QUICKSTART.md and INTEGRATIONS.md were largely current but lacked cross-references to the rest of the documentation suite, creating navigation dead ends.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-25] Ground-up rewrite of CORE.md, DESIGN.md, and GLOSSARY.md

**Changed:** Rewrote all three human-facing documentation files under `HUMANS/docs/` to reflect the current state of the system:
- **GLOSSARY.md:** Replaced flat 20-term alphabetical list with a 6-section, ~45-term organized glossary. New sections: Architecture & Structure, Memory Lifecycle, Working Memory, Governance & Security, MCP Tool Surface. Added terms for format/runtime layer, platform adapter, agent-bootstrap.toml, browser views, scratchpad, plans, governed preview, version token, staged transaction, tool tiers, identity churn tracking, and more.
- **CORE.md:** Expanded from 8 design decisions to 12. Added decisions for MCP governed tool access (73 tools, 3 tiers), browser views (File System Access API, 7 pages), plans as first-class objects, and scratchpads bridging sessions. Updated existing decisions to reference HOME.md, agent-bootstrap.toml, session modes, token budgets, three-tier change model, and governed preview workflows. Updated "When to read which document" to include HELP.md, MCP.md, INTEGRATIONS.md.
- **DESIGN.md:** Renamed from "Agent Memory Seed" to "Engram". Updated Principles 2 (platform adapters) and 3 (progressive disclosure with browser wizard and collaborative onboarding). Added new subsections: "The governed-write model" (preview/commit, version tokens, change classes) and "Plans as durable work contexts." Added browser dashboard to use cases. Restructured Part III into "Recently Realized" (CI validation, expanded profiles, browser views, MCP health, collaborative onboarding, knowledge graph, git hooks) plus remaining future directions. Rewrote Part IV MCP section from a 5-function sketch to the actual 73-tool, three-tier surface.

All cross-references validated: 18 links across the three files, all resolving correctly. docs.html viewer compatibility confirmed (filename-based, content-agnostic). No stale "Agent Memory Seed" terminology remaining.

**Reasoning:** The three docs were written when the system was a template-stage seed project. They predated the MCP server (73 tools), browser views (7 pages), plan system, collaborative onboarding, governed-write model, and agent-bootstrap.toml. Users reading these files were getting a picture of a system that no longer existed. The rewrite brings them into alignment with the actual system architecture.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-24] Markdown section-link support in browser views

**Changed:** Expanded the shared browser markdown renderer in `HUMANS/views/engram-utils.js` to generate stable heading IDs, support same-document section links like `#heading`, and preserve cross-document anchors like `other.md#heading` through the internal cross-reference callback. Updated `knowledge.html` and `docs.html` so cross-reference navigation can open a target document and scroll to the requested section. Updated `graph.js` and its JS tests so file-level reference extraction accepts `.md#section` links without dropping the underlying document edge.

**Reasoning:** The shared renderer only recognized bare `.md` document links. As soon as a markdown link included a fragment, the renderer either treated it as a generic external URL or left it inert, which meant section links inside docs and knowledge files could not be followed. Adding anchor-aware parsing at the shared utility layer fixes the behavior consistently across the browser views and keeps the graph/reference tooling aligned with the new link format.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-24] Shared markdown renderer and views consolidation

**Changed:** Extracted the markdown renderer from knowledge.html into a shared `Engram.renderMarkdown()` function in `engram-utils.js`. The shared renderer is DOM-safe (no innerHTML), supports headings, bold, italic, inline code, links, fenced code blocks, tables, nested lists, blockquotes, horizontal rules, and KaTeX math (display blocks and inline). It accepts an optional `onXrefClick` callback for cross-reference navigation. Replaced the 4 separate markdown renderers (knowledge.html, projects.html, skills.html, users.html) with calls to the shared version. Eliminated the unsafe innerHTML-based regex renderers in skills.html and users.html. Added KaTeX CDN (v0.16.21 with SRI integrity) to all HTML `<head>` sections (previously only knowledge.html). Moved `.math-display` CSS to `engram-shared.css`. Updated HUMANS/README.md to document skills.html, users.html, graph overlay, and KaTeX. Updated QUICKSTART.md to list all five browser views.

**Reasoning:** The four independent markdown renderers had diverged in quality and feature coverage — knowledge.html had full math support and DOM-safe construction, projects.html lacked math, and skills/users.html used regex+innerHTML which is an XSS risk even with escapeHtml pre-processing. Consolidating to a single shared renderer ensures consistent rendering quality, eliminates the innerHTML security concern for markdown content, and enables KaTeX math rendering across all views.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-23] Views styling polish, design tokens, and documentation

**Changed:** Introduced CSS custom properties (`:root` design tokens) in `engram-shared.css` for the full color palette, border radii, shadow tokens, and monospace font stack — replacing ~60 hardcoded hex values scattered across four HTML files. Added subtle box-shadows to all card/panel components (`--shadow-card` resting, `--shadow-hover` on interactive lift). Fixed inconsistent inline-code styling: removed the pink `color: #e11d48` in knowledge.html, unified code background to `--color-code-bg` across all pages, added shared `code` rule with monospace font stack. Added 🧠 SVG favicon to all four HTML pages. Added "View all →" link to the Knowledge Base panel header in dashboard.html (was missing — projects panel already had one). Expanded `HUMANS/README.md` from a 2-line stub to a full file inventory, architecture overview, and navigation diagram for the views. Updated `HUMANS/docs/QUICKSTART.md` to mention knowledge and project viewers.

**Reasoning:** The four viewer pages had diverged in styling conventions — hardcoded colors, inconsistent code block treatment (knowledge used pink text, projects used a different background, dashboard had yet another), and no shared shadow/depth system. CSS custom properties establish a single source of truth that makes future theming (e.g. dark mode) trivial. The documentation gap meant neither humans nor agents knew the views existed or how they related to each other.

**Approved by:** user (batch-reviewed 2026-03-27)

## [2026-03-23] Projects dashboard and knowledge cross-reference navigation

**Changed:** Added `HUMANS/views/projects.html` — standalone project viewer with card-based list and full detail view (metadata bar, focus callout, collapsible question cards, YAML plan timeline with phase indicators, inline notes viewer). Added click-through navigation from the dashboard projects panel to projects.html. Added cross-reference navigation to knowledge.html: clickable `related:` frontmatter entries, inline markdown links to other knowledge files, and backtick file references. Updated dashboard.html with "View all →" link in the projects panel header and clickable project rows.

**Reasoning:** The dashboard provided a summary of projects and knowledge but no way to drill into detail. The projects viewer enables browsing the full project tree (questions, plans, notes) without needing an agent session. Cross-reference navigation in the knowledge viewer surfaces connections between knowledge files that were previously invisible to users.

**Approved by:** user (batch-reviewed 2026-03-27)

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
