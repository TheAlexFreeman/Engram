---
title: Cold-Start Discoverability Roadmap
audience: Alex + future agents working in Engram
status: draft
created: 2026-04-16
---

# Cold-Start Discoverability Roadmap

A prioritized, schedulable plan to fix the cold-start experience for agents picking up work on an existing Engram project. Extends existing primitives (`memory_session_bootstrap`, `memory_context_project`, `SUMMARY.md`, `memory_route_intent`) rather than building parallel conventions.

## TL;DR

The intended cold-start flow already exists in Engram: an agent calls `memory_session_bootstrap`, reads `memory/working/projects/SUMMARY.md` for the navigator, reads `memory/working/projects/<name>/SUMMARY.md` for a per-project briefing, then calls `memory_context_project(project=<name>)` for enriched context. That flow is broken end-to-end today because `memory_context_project` reliably times out, `memory_route_intent` doesn't map cold-start intents to it, and nothing in `CLAUDE.md` points agents at the flow at all. The seven items below fix that in roughly 9–12 working days (plus a 1–2 day buffer on P0-A if instrumentation surfaces unexpected hot spots), sequenced so the end-to-end path works after the three P0 items (~5 days) and gets enriched in P1.

- **P0 (~5d):** make `memory_context_project` fast and resilient, route agents into the flow from `CLAUDE.md`, and teach `memory_route_intent` to recognize cold-start intents.
- **P1 (~3d):** extend per-project `SUMMARY.md` with the fields a cold-starting agent actually needs, add snapshot-freshness frontmatter to `IN/` material, and document the project-folder lifecycle in one README.
- **P2 (~2d):** make `memory_read_file` degrade gracefully on large files instead of handing back an inaccessible OS temp path.

## Current state

**Intended flow.** When an agent is told "work on project X," it is supposed to:

1. Call `memory_session_bootstrap` — returns capabilities, session health, and active plans each carrying a `resume_context` pointer like `memory_context_project(project=<name>)`.
2. Read `memory/working/projects/SUMMARY.md` — an auto-generated navigator table covering all projects (Status, Mode, Open Qs, Focus, Last activity).
3. Read `memory/working/projects/<name>/SUMMARY.md` — per-project briefing with frontmatter (`status`, `cognitive_mode`, `current_focus`, `open_questions`, `last_activity`, `origin_session`, `trust`, `source: agent-generated`, `active_plans`) and a Description body.
4. Call `memory_context_project(project=<name>)` — assembles project summary + current plan + plan sources + `IN/` manifest + session notes into one ~24KB Markdown + JSON response.

**What works today.** `memory_session_bootstrap` returns a usable bundle. Projects-level `SUMMARY.md` is generated with the right shape (8 projects tracked, last regenerated 2026-04-15). Per-project `SUMMARY.md` files exist and use the agent-generated convention. `memory_generate_summary` exists and produces the navigator on demand.

**What's broken end-to-end.**

- `memory_context_project` reliably times out at 60s on `rate-my-set` (observed twice in a single session). The 60s ceiling is the MCP transport/client limit, not a server-side budget. The tool itself runs unbounded with no instrumentation, no graceful degradation, no cache, and no time budget. Implementation at `core/tools/agent_memory_mcp/tools/read_tools/_context.py` (lines 732–1090) is sequential file reads + YAML parsing with no obvious hot spot — meaning we don't know yet *why* it's slow and need to instrument before optimizing.
- `memory_route_intent` returns `ambiguous: true` for a natural cold-start query ("I am cold-starting work on the rate-my-set project and need a briefing on its current state"). `_route_intent_candidates()` in `core/tools/agent_memory_mcp/tools/read_tools/_helpers.py` is keyword-scored but has no entries for cold-start intents. The routing surface exists; the coverage doesn't.
- Repo `CLAUDE.md` says "prefer agent-memory MCP tools for memory reads" but never tells the agent which tool to call when a user names a project, or that `memory/working/projects/` is the entry point. Cold-starting agents therefore fall back to filesystem listing and miss the flow entirely.
- Per-project `SUMMARY.md` is shaped like a description, not a briefing. It's missing the fields a cold-starting agent actually needs: subfolder legend (what `IN/`, `docs/`, `plans/`, `notes/` each hold), canonical-source pointer (for projects like `rate-my-set` where the real code lives upstream and `IN/` holds a snapshot), and a "how to continue" breadcrumb pointing at the currently-active plan, `questions.md`, and pending reviews.
- `IN/` snapshots carry no `snapshot_taken_at` or `reflects_upstream_as_of` frontmatter, so agents silently treat stale material as current. No governed ingestion-time autopopulation either.
- The `IN/OUT/docs/plans/notes/` folder lifecycle is documented nowhere. A first-time agent has to infer purpose from contents.
- `memory_read_file` returns an OS temp-file path for files >20 KB (`_READ_FILE_INLINE_THRESHOLD_BYTES`, written in `_inspection.py` with `delete=False`, no pagination). On a Windows-hosted MCP serving a Linux-sandbox client, that path doesn't cross the filesystem boundary, so the file becomes unreadable. Cold-start contexts hit this when pulling larger project docs.

**Terms used throughout.**

- *Primitives* = the existing tools and artifacts that together form the cold-start surface: `memory_session_bootstrap`, `memory_context_project`, `memory_route_intent`, `memory_read_file`, and the `SUMMARY.md` convention at projects/ and per-project level.
- *Soft convention* = a documented, agent-seeded pattern (frontmatter fields, file shapes) that is not enforced by a write-time validator. Legacy material missing the convention is tolerated; readers degrade gracefully. Contrasts with *hard enforcement*, which rejects non-conforming writes.
- *Governed write* = a write that passes through the agent-memory MCP's change-class / preview / approval pipeline (see `core/governance/`). Direct filesystem writes are ungoverned and are avoided except for scratchpads.
- *`resume_context`* = a JSON object returned inside `memory_session_bootstrap`'s active-plan entries, containing `{tool: <tool_name>, arguments: {...}}`. Agents call the referenced tool with the referenced arguments to resume work on that plan.
- *`cognitive_mode`* = a per-project frontmatter field on `SUMMARY.md`, currently taking values `exploration`, `planning`, or `execution`. Signals how much the project is actively being shaped vs. mechanically executed. Used in routing and freshness heuristics.

**Design principles applied below.**

- *Extend existing primitives.* Don't parallel-build. `SUMMARY.md` is the briefing artifact; `memory_context_project` is the enrichment tool; `memory_session_bootstrap` is the session entry point.
- *Soft conventions over hard enforcement.* New frontmatter fields (`snapshot_taken_at`, cold-start fields in `SUMMARY.md`) are documented and agent-seeded. Soft conventions get adopted; hard enforcement rots.
- *Agent-generated, for agents.* Per-project `SUMMARY.md` is written by agents on project creation and refreshed by agents on material change. Humans don't hand-author these.
- *Diagnose before optimizing.* The context_project fix starts with instrumentation, not a rewrite.

## Roadmap

Items are ordered by priority. P0 items are blockers on the end-to-end cold-start flow working at all. P1 items enrich what works once P0 is in place. P2 items remove remaining failure modes.

Each item: **Problem** / **Proposal** / **Implementation** / **Effort** / **Dependencies** / **Verification notes**.

### P0-A: Fix `memory_context_project` latency

**Problem.** The tool times out at 60s on at least one real project (`rate-my-set`). Because `memory_session_bootstrap` returns `resume_context` pointers at this tool, the intended cold-start flow is broken end-to-end whenever the tool is slow. No current instrumentation explains why; the implementation does sequential file reads + YAML parsing with no obvious hot spot.

**Proposal.** Diagnose before optimizing. Instrument the tool, reproduce the timeout across all 8 active projects, then apply the smallest set of changes that brings p95 under 2s — a combination of bounded sections, a content-hash keyed on-disk cache, and opt-in enrichment for sections that aren't needed for cold-start.

**Headline fix in one sentence.** Make the default cold-start path return a cached, bounded project bundle in under 500ms, keep the slow full-enrichment path behind opt-in flags, and fail-fast with partial content when the 5s internal budget is exceeded.

**Implementation.**

1. *Add per-section span timing.* Reuse `record_trace` infrastructure from `core/tools/agent_memory_mcp/plan_trace.py`. Wrap each assembly step in `_context.py` (plan selection, plan sources, `_render_in_manifest()`, session notes lookup, markdown rendering) with a named span. Include total and per-span ms in the returned JSON metadata under a `timings` key. Surface aggregate timings through `memory_session_health_check`.
2. *Reproduce across all 8 projects.* Script a harness that calls `memory_context_project` for every project listed in `memory/working/projects/SUMMARY.md` and logs per-span timings. Commit the harness under `core/tests/` so latency regressions are catchable.
3. *Add a hard time budget with graceful degradation.* Enforce a server-side 5s budget (separate from MCP transport timeout). When exceeded mid-assembly, return partial content with a `truncated: true` flag and a `sections_omitted: [...]` list in metadata. Better to return partial-fast than time-out.
4. *Bound expansive sections.* `_render_in_manifest()` currently enumerates every `IN/` file with full frontmatter — cap to the 20 most recent by `last_activity`, add a `more_in_items: N` counter, and point callers at `memory_list_folder` for the full listing. Same treatment for plan-sources (cap total chars to ~8KB or file count to 10, whichever smaller).
5. *Make heavy sections opt-in.* Split the `include_plan_sources` flag into finer toggles: `include_plan_sources`, `include_in_manifest`, `include_session_notes`. Default `include_plan_sources=False` and `include_in_manifest="summary"` so cold-start callers get the fast path by default. Bootstrap's `resume_context` should not request heavy sections.
6. *Add an on-disk cache keyed by project content hash.* After a successful run, persist the rendered bundle under `memory/working/projects/<name>/.context-cache.json` with a version token derived from `git rev-parse HEAD:memory/working/projects/<name>` (or mtimes of tracked files if cheaper). On the next call, if the hash matches, return cached content with a `cache_hit: true` flag. Invalidation is implicit — any write under the project subtree changes the hash. Pre-warm on write: after any governed write that touches a project, regenerate the bundle so the next read is cached. Hook into the existing post-write pipeline rather than adding a separate scheduler.
7. *Ship a `memory_context_project_lite` fast-path as a fallback.* A strictly-bounded version that reads only `SUMMARY.md` + active plan names/IDs. Guaranteed <500ms. Use this when bootstrap needs guaranteed responsiveness, when context_project has exceeded its budget twice in a row, or as an explicit agent choice. Not a replacement — a safety valve.

**Effort.** 3–5 days. Instrumentation and repro day one; bounding and opt-in flags day two; cache + pre-warm day three; `_lite` fallback + cleanup day four-to-five.

**Dependencies.** None blocking. Instrumentation (step 1) unblocks everything else and should ship standalone first.

**Verification notes.** A fixture project with known contents (e.g., `rate-my-set` at a pinned commit) with a target of p95 <2s, p50 <500ms after fix. The timing harness in step 2 becomes the regression test. Cache-hit rate should be >80% for cold-start queries during typical sessions.

**Risks to watch during implementation.**

- *Cache invalidation granularity.* Whole-subtree hashing (step 6) is safe but can cause spurious misses when unrelated files under the project change (e.g., `operations.jsonl` appends). If hit rate drops below 50% in real sessions, narrow the hash to the files `context_project` actually reads. The open question in the later section documents this trade-off.
- *Partial-content UX.* When the 5s budget is exceeded mid-assembly (step 3), agents receive `truncated: true` with sections omitted. Downstream callers (including `bootstrap`'s `resume_context` flow) must handle partial bundles gracefully. Add an integration test that verifies the partial-bundle path doesn't break existing agent workflows.
- *Buffer on effort.* The 3–5 day range assumes instrumentation reveals an actual hot spot that bounding/caching fixes. If timings show the work is genuinely I/O-bound or dominated by YAML parsing of pathological plan files, step 3's time budget plus step 7's `_lite` fallback still unblock cold-start but steps 4–6 may need redesign. Budget an additional 1–2 days of buffer if the instrumentation surprises us.

### P0-B: Route agents into the cold-start path from `CLAUDE.md`

**Problem.** The repo-level `CLAUDE.md` is the first file agents read in an Engram session. It currently mentions the agent-memory MCP tools but never tells an agent what to do when a user names a project. Agents default to filesystem listing, miss `memory_session_bootstrap` entirely, and never discover `memory/working/projects/SUMMARY.md`. This is the cheapest possible fix and unblocks adoption of everything else in this roadmap.

**Proposal.** Add one paragraph to `CLAUDE.md` documenting the cold-start flow, plus a one-pager `memory/working/projects/README.md` that P1-C will build out further. The goal is that an agent reading only `CLAUDE.md` knows exactly which two or three tools to call when a user says "work on project X."

**Implementation.**

1. *Edit `CLAUDE.md`.* After the existing "prefer agent-memory MCP tools" sentence, insert the following paragraph verbatim (tune wording during verification):

   > **Cold-starting on a project.** When the user names a project, call `memory_session_bootstrap` first — active plans come back with `resume_context` pointers ready to dereference. Then read `memory/working/projects/SUMMARY.md` for the navigator of all projects, and `memory/working/projects/<name>/SUMMARY.md` for the per-project briefing (subfolder legend, canonical source, how-to-continue). Finally, call `memory_context_project(project=<name>)` for the enriched bundle (current plan, plan sources, `IN/` manifest, session notes). If you don't know which tool fits, call `memory_route_intent` with what you're trying to do. Per-project `SUMMARY.md` is the agent-maintained briefing artifact — update it when the project's cognitive mode, current focus, or active plans change.
2. *Seed a `memory/working/projects/README.md` stub.* One paragraph explaining `projects/SUMMARY.md` as the navigator and pointing at the per-project subfolder layout. P1-C fills in the full lifecycle detail. Referenced from `CLAUDE.md` so the doc path is discoverable.
3. *Verify against a blank agent.* Start a fresh session, prompt "work on rate-my-set," and check that the agent's first three tool calls are `memory_session_bootstrap`, a read on `projects/SUMMARY.md`, and a read on `rate-my-set/SUMMARY.md` (or `memory_context_project`). Iterate on the `CLAUDE.md` wording until this is reliable.

**Effort.** 0.5 day — ~30 minutes of writing, the rest in verification iteration.

**Dependencies.** None. Can ship before P0-A, but is less useful until P0-A lands because the resume_context pointer will still time out.

**Verification notes.** Reader-test: start a fresh Claude session with no prior context, prompt it to "work on rate-my-set," and inspect its first three tool calls. Add this scenario to the fixture suite so future `CLAUDE.md` edits are checked for regression.

### P0-C: Seed `memory_route_intent` with cold-start intents

**Problem.** `memory_route_intent` is the intended natural-language entry point — agents that know the task goal but not the tool name can describe what they want and get a recommendation. The routing table in `_route_intent_candidates()` (`core/tools/agent_memory_mcp/tools/read_tools/_helpers.py`) uses keyword-based scoring. It has no entries for cold-start phrasing, so a reasonable query like "brief me on rate-my-set" returns `ambiguous: true`. Agents then give up on routing and fall back to filesystem listing.

**Proposal.** Add keyword-scored candidates for the handful of cold-start phrasings agents actually use, mapped to the primitives that actually serve them.

**Implementation.**

1. *Add candidate blocks in `_route_intent_candidates()`* for these intent shapes, each with a regex to extract the project name where present:
   - "brief me on X", "briefing on X", "summary of X" → `memory_context_project(project=X)`, score ~0.95
   - "get me up to speed on X", "onboard me to X", "cold start on X", "start work on X" → `memory_context_project(project=X)`, score ~0.93
   - "what projects are active", "list projects", "what am I working on" → read `memory/working/projects/SUMMARY.md` (surface via a returned read target, not a tool call), score ~0.92
   - "resume work", "continue where I left off" → `memory_session_bootstrap`, score ~0.90
2. *Project name extraction.* Use a small regex matched against the keys of the projects index (`projects/SUMMARY.md` frontmatter / directory listing). If the named project doesn't exist, still return the operation with a warning rather than failing routing entirely.
3. *Fallback to `memory_session_bootstrap`* when intent looks cold-start-ish but no project is named. Score ~0.85.
4. *Add an intent-routing fixture* under `core/tests/` with ~20 natural-language inputs and expected top operations. Becomes the regression test for future routing edits.

**Effort.** 1 day. Keyword blocks are copy-paste once the pattern is set; most time is on extraction regex edge cases and fixture coverage.

**Dependencies.** P0-B (CLAUDE.md pointer) is more useful with this in place, because `CLAUDE.md` can tell agents "if in doubt, call `memory_route_intent` with what you want." Order P0-C before P0-B's final wording pass.

**Verification notes.** The fixture in step 4 is the acceptance test. Also, re-run the original failing query from this session ("I am cold-starting work on the rate-my-set project and need a briefing on its current state") and confirm `recommended_operation` is `context_project` with `path.project=rate-my-set`.

### P1-A: Extend per-project `SUMMARY.md` with cold-start fields

**Problem.** Per-project `SUMMARY.md` today is a description plus minimal frontmatter (`status`, `cognitive_mode`, `current_focus`, `open_questions`, `last_activity`, `origin_session`, `trust`, `source`, `active_plans`). That's a project card, not a cold-start briefing. A fresh agent still has to infer the subfolder layout from directory listing, guess which files are canonical vs. staged, and hunt for the active plan. Three small additions close the gap.

**Proposal.** Extend the per-project `SUMMARY.md` template with three cold-start-critical sections: a subfolder legend, a canonical-source pointer, and a "how to continue" breadcrumb. Update `memory_generate_summary` to produce these sections when generating a new `SUMMARY.md`. Soft convention — existing projects can be back-populated lazily by agents as they're touched.

**Implementation.**

1. *Extend the template.* After the Description body, add three named subsections:
   - **Layout**: one-line-per-subfolder legend, e.g., `IN/ — staged external material; OUT/ — emitted decisions and artifacts; docs/ — reference material; plans/ — active and completed plans; notes/ — working notes; questions.md — open questions.` Lifted verbatim from the P1-C README where possible so both stay in sync.
   - **Canonical source** (optional, project-specific): for projects like `rate-my-set` where real code lives upstream, a pointer like `Canonical source: https://github.com/<org>/<repo> at commit <sha>. Contents under IN/ are a snapshot staged on <date>; treat as read-only.` If no upstream exists (the project is self-contained in the memory repo), omit this section.
   - **How to continue**: three or four pointers — the currently-active plan path, `questions.md` if open questions exist, `IN/` most-recent items by date, last chat summary if one exists. Machine-parseable: one link per line.
2. *Update `memory_generate_summary`.* The generator in `core/tools/agent_memory_mcp/tools/read_tools/_generation.py` reads headings and first paragraphs today. Extend it to produce the three new sections from available signals: plans folder for the active plan, `questions.md` existence for the open-questions line, `IN/` manifest for most-recent items, `operations.jsonl` for last activity. Keep the generator read-only (it returns a draft, not a committed file) — the agent that calls it is responsible for writing the returned draft to `SUMMARY.md` via a governed write.
3. *Back-populate existing projects opportunistically.* When an agent touches an existing project (reads or writes), it should call `memory_generate_summary`, diff the draft against the current `SUMMARY.md`, and commit the updated version if fields have drifted. No batch migration — per-project regeneration amortizes across normal work and keeps the agent's attention on the content.
4. *Teach `memory_context_project` to favor these sections.* In the assembly loop, the Project Summary section should preserve the Layout, Canonical source, and How to continue subsections intact even under budget pressure. These are load-bearing for cold-start; the Description body is not.

**Effort.** 1.5 days. Template and generator changes one day; opportunistic back-populate is not counted (amortized across future project work); context_project update another half-day.

**Dependencies.** P1-C (the lifecycle README) should land first so the Layout subsection can cite it. P0-A's graceful degradation should be in place so the new sections are actually preserved under budget.

**Verification notes.** Generate a fresh `SUMMARY.md` for a test project and confirm all three sections are produced. Reader-test: a fresh Claude should be able to answer "what's in this project" and "where's the canonical source" from the briefing alone.

### P1-B: Add `IN/` snapshot-freshness frontmatter

**Problem.** Material in `IN/` often comes from external systems (code repos, shared docs, meeting notes) and is staged at a point in time. There's currently no frontmatter signaling when material was staged or when it last reflected upstream. Agents silently treat old snapshots as current. In this session, `IN/better-base-dev/` contained a Django codebase snapshot, and I had to ask the user whether the snapshot was current — it should have been self-evident from frontmatter.

**Proposal.** Add two frontmatter fields to `IN/` material, autopopulated by the ingestion pathway: `snapshot_taken_at: YYYY-MM-DD` (mandatory on write) and `reflects_upstream_as_of: YYYY-MM-DD` (optional, set when the snapshot is re-verified against upstream). Surface these in the `IN/` manifest and the `memory_context_project` response.

**Implementation.**

1. *Define the frontmatter contract.* Update the frontmatter schema docs under `core/governance/` (or wherever frontmatter types are defined) to include the two new fields. Soft convention — missing fields on legacy material are fine; readers degrade to "freshness unknown" rather than erroring.
2. *Autopopulate on ingestion.* `memory_stage_external` and any other tool that writes into `IN/` should set `snapshot_taken_at` to the current date automatically. If the caller provides a more specific timestamp (e.g., from upstream git commit date), prefer that. `reflects_upstream_as_of` is set only by explicit re-verification operations.
3. *Expose in `IN/` manifest.* `_render_in_manifest()` should include freshness in the per-item line: `rate-my-set-dev/Dockerfile  (snapshot 2026-04-14, upstream 2026-04-12)`. Visual trigger for stale material.
4. *Expose in `memory_context_project`.* The `IN/` section of the context bundle should include a freshness summary: "IN/ contains N items staged between <oldest> and <newest>." Items older than ~60 days should be flagged for review.
5. *Add a `memory_check_knowledge_freshness`-style pass.* There's already `memory_check_knowledge_freshness` in the tool surface — wire it to check `IN/` freshness specifically and surface items where `snapshot_taken_at` is older than `reflects_upstream_as_of + threshold` or where both are absent.

**Effort.** 1 day. Frontmatter schema update is fast; autopopulation hook is one function; exposure is two touches.

**Dependencies.** None. Ships independent of P0-A because it doesn't affect latency. Most useful after P1-A so the "How to continue" section can reference stale items.

**Verification notes.** Stage a new external doc via `memory_stage_external` and confirm the frontmatter is set automatically. Run `memory_check_knowledge_freshness` on a project with mixed-age `IN/` material and confirm stale items are flagged.

### P1-C: Document the `IN/OUT/` lifecycle

**Problem.** Every project folder has a consistent substructure (`IN/`, `OUT/` at the projects root, `docs/`, `plans/`, `notes/`, `SUMMARY.md`, `questions.md`, `operations.jsonl`) but the meanings and lifecycles are documented nowhere. First-time agents infer from contents; it works but costs tool calls and risks misinterpretation. `OUT/` sitting at the projects root (not per-project) is especially non-obvious.

**Proposal.** One README at `memory/working/projects/README.md` that defines each subfolder's purpose, who writes into it, who reads from it, and the expected lifecycle. Referenced from `CLAUDE.md` (P0-B) and cited by the Layout subsection of per-project `SUMMARY.md` (P1-A).

**Implementation.**

1. *Write the README.* Sections: Overview, Folder layout, Per-project substructure, Lifecycle, Conventions. Keep it under 400 lines — this is a routing doc, not a spec. Concrete contents:
   - `projects/SUMMARY.md` — auto-generated projects navigator. Regenerated by `memory_generate_summary`; the navigator can go stale between regenerations (on-demand only today).
   - `projects/OUT/` — emitted decisions and artifacts that cross project boundaries. Writes are governed.
   - `projects/ACCESS.jsonl` — access audit log.
   - `projects/<name>/SUMMARY.md` — agent-generated per-project briefing.
   - `projects/<name>/IN/` — staged external material. Frontmatter carries `snapshot_taken_at`, `reflects_upstream_as_of` (P1-B). Read-only from agents' perspective — upstream is the source of truth.
   - `projects/<name>/OUT/` — emitted artifacts scoped to this project.
   - `projects/<name>/docs/` — reference material produced within the project (stable, citation-grade).
   - `projects/<name>/plans/` — active and completed plans (YAML, managed by `memory_plan_*` tools).
   - `projects/<name>/notes/` — working notes; lower-trust than `docs/`, promoted upstream via the curation pipeline.
   - `projects/<name>/questions.md` — open questions, one per bullet. Consumed by cold-start agents.
   - `projects/<name>/operations.jsonl` — append-only operations audit.
2. *Cite from `CLAUDE.md`.* P0-B's README stub becomes a one-paragraph pointer at this file.
3. *Cite from per-project `SUMMARY.md`.* P1-A's Layout subsection should include a one-liner like "See `memory/working/projects/README.md` for the full lifecycle."
4. *Keep the README agent-readable.* Short sentences, consistent structure, no marketing tone. This is scaffolding, not documentation in the glossy sense.

**Effort.** 0.5 day. Most of the content exists scattered; this is consolidation.

**Dependencies.** None. Ships any time. Most useful before P1-A so the Layout subsection can cite a real doc rather than a placeholder.

**Verification notes.** Reader-test: fresh Claude is given only `CLAUDE.md` + the new README + a project's `SUMMARY.md`. Ask it "where would I put a new decision artifact scoped to this project?" — it should say `projects/<name>/OUT/` without guessing.

### P2: Graceful large-file handling in `memory_read_file`

**Problem.** Files above the 20 KB inline threshold (`_READ_FILE_INLINE_THRESHOLD_BYTES` in `core/tools/agent_memory_mcp/tools/read_tools/_helpers.py`) are written to an OS temp file by `_inspection.py` with `delete=False`, and the tool returns the temp-file path in `result["temp_file"]`. When the MCP server and the agent's sandbox run on different filesystems (Windows MCP host, Linux agent sandbox), that path is not resolvable from the agent side — the file is effectively unreadable. I hit this on two docs in the rate-my-set project (toolchain.md at >20 KB, roadmap.md at ~23 KB) and worked around it by relying on search hits.

**Proposal.** Stop returning temp-file paths across a sandbox boundary. Instead, return an inline excerpt by default and support paginated reads via offset and limit parameters. Increase the inline threshold where practical. Keep `temp_file` as an opt-in for same-filesystem callers that genuinely want the whole file at once.

**Implementation.**

1. *Raise the inline threshold.* 20 KB is conservative. 64 KB covers virtually all docs in the memory tree without hurting response sizes. Revisit after measuring actual distribution.
2. *Add `offset_bytes` and `limit_bytes` parameters to `memory_read_file`.* When set, return a byte-range slice inline with a `total_bytes` field and a `has_more: true` flag if truncated. Semantics match standard paginated APIs.
3. *Change the default for oversize files* to return the first `limit_bytes` (default 64 KB) of content inline plus pagination metadata. `temp_file` becomes opt-in via a `prefer_temp_file: true` parameter, used only when caller knows it's on the same filesystem.
4. *Surface the pagination hint in the response.* If a file is truncated, metadata includes `next_call_hint: {"offset_bytes": <n>, "limit_bytes": <n>}` so agents can trivially paginate without re-deriving offsets.
5. *Deprecate `temp_file` returns from cross-filesystem deployments.* Detection in priority order: (a) an explicit `AGENT_MEMORY_CROSS_FILESYSTEM=1` env var or config flag — most reliable, caller sets it per deployment; (b) mismatch between the server's temp-dir path root (`/tmp` vs. `C:\...`) and a caller-reported sandbox root, passed in as an optional `sandbox_fs: "linux" | "windows"` request argument; (c) heuristic fallback — if the temp file suffix contains characters the caller-reported platform can't resolve, suppress. When any detector trips, force paginated inline response and omit `temp_file` entirely. Document the env var in the deploy notes.

**Effort.** 2 days. Mostly parameter plumbing and test coverage. One day implementation, one day testing across the file-size distribution and across same-filesystem / cross-filesystem configurations.

**Dependencies.** None. Independent fix, can ship any time. Most useful once P0-A lands so large project files don't accidentally blow cold-start budgets.

**Verification notes.** Read a known >30 KB file and confirm the response is inline with pagination metadata. Verify `temp_file` is suppressed when cross-filesystem is detected. Add a fixture covering sub-threshold, at-threshold, and over-threshold sizes to the read-tools test suite.

## Non-goals

The items below are deliberately out of scope. They came up during brainstorming and are valid work — they just aren't this roadmap's work.

- **Rewriting `memory_context_project` from scratch.** The implementation is shaped correctly; it's unbounded and uncached but not architecturally wrong. Diagnose and patch (P0-A), don't rebuild.
- **Parallelizing section assembly.** The investigation showed no obvious hot spot, so parallel I/O is premature optimization before diagnosis. Revisit after P0-A step 1 if timings show I/O-bound behavior.
- **Hard-validating frontmatter on write.** P1-B's `snapshot_taken_at` and P1-A's new `SUMMARY.md` fields are soft conventions. Adding a write-time validator that rejects missing fields is a larger governance change and creates churn for existing projects. Soft conventions + agent-generated defaults get adopted; hard enforcement rots.
- **Auto-regenerating `projects/SUMMARY.md` on every write.** Tempting, but the navigator can reasonably go stale for a few hours or days. If the regeneration cost is trivial, fold it into P0-A's cache pre-warm. If it's not, leave it on-demand and fix it separately.
- **Building a new MCP tool for cold-start.** The existing surface (`memory_session_bootstrap` + `memory_context_project` + `memory_route_intent` + `memory_read_file`) is sufficient once P0 items land. Adding `memory_cold_start(project)` would be a parallel convention — exactly the thing this roadmap rejects.
- **Replacing `memory_context_project` with a committed static bundle.** Discussed and dropped. Loses freshness guarantees, shifts the problem to regeneration cadence, and doesn't solve the reader-side latency any better than a cache hit. Cache invalidation is the right shape.
- **Onboarding for external contributors.** This roadmap targets Alex + future agents inside the Engram repo. External-contributor docs are a different audience and belong in a separate initiative.
- **Human-facing docs refresh.** `HUMANS/` is not touched. Agents are the primary audience here; humans can follow along via the same artifacts without a separate doc track.

## Open questions

Decisions deferred to implementation time rather than pre-litigated here. Each item below needs resolution before or during the implementation of its referenced roadmap item.

- **P0-A cache invalidation granularity.** Is the content hash computed over the whole project subtree, or only the files `context_project` actually reads? Subtree is simpler and safer; per-input is cheaper but couples the cache to the tool's internal traversal. Start with subtree; optimize later if needed.
- **P0-A cache storage location.** Per-project `.context-cache.json` inside the project folder is simple but pollutes the tracked tree. An out-of-tree cache directory (e.g., `memory/.cache/context/<project>.json`) is cleaner but needs ignore-list discipline. Decide based on what the existing `SkillResolver` cache convention does.
- **P0-A whether to gate `_lite` behind a flag or make it a separate tool.** Separate tool is more discoverable (shows up in tool listings); flag is a smaller API surface. Leaning separate tool; confirm during implementation.
- **P0-C routing confidence threshold.** Scores in `_route_intent_candidates()` currently go 0.90–0.98. Cold-start scores proposed at 0.90–0.95. Is there a minimum confidence below which the router should prefer "ambiguous" even with a top match? If so, what's the threshold?
- **P1-A canonical-source format.** For projects with external upstreams (`rate-my-set` → GitHub, potentially others), is there a standard shape? `url` + `commit` + `staged_at` covers git. Non-git sources (Google Docs, Slack, Linear) need different shape. Defer until more than one non-git example exists.
- **P1-B threshold for "stale" IN/ material.** 60 days is a guess. Should it be per-project, global, or derived from the project's `cognitive_mode`? Exploration-mode projects can tolerate older snapshots; execution-mode projects cannot.
- **P1-C scope of the lifecycle README vs. existing governance docs.** `core/governance/` already covers some of this. Avoid duplication — the projects README should be navigation, not policy. Audit existing governance docs before writing and cite where they overlap.
- **P2 pagination API shape.** Byte offsets are simple but awkward for UTF-8. Line offsets are agent-friendly but require the server to pre-split. Start with byte offsets (matches stdlib `read`), revisit if agents complain.
- **Rollout signaling.** When a new cold-start feature lands (e.g., P1-A's extended `SUMMARY.md` template), how do existing per-project summaries get back-populated? Opportunistic-when-touched is the default; is a one-time agent-driven migration pass worth budgeting? Probably not for the 8 current projects — revisit if project count grows.

## Appendix: reference paths and tools

Existing artifacts and code surfaces this roadmap builds on. All paths are repo-relative unless noted.

**Entry-point tools.**

- `memory_session_bootstrap` — session-start bundle (capabilities, session health, active plans with `resume_context` pointers, pending reviews). Works today.
- `memory_context_project(project=<name>)` — per-project enrichment bundle. Implementation at `core/tools/agent_memory_mcp/tools/read_tools/_context.py` (lines 732–1090). Reliably times out; target of P0-A.
- `memory_route_intent(intent=<str>)` — natural-language intent routing. Scoring in `_route_intent_candidates()` at `core/tools/agent_memory_mcp/tools/read_tools/_helpers.py`. Missing cold-start entries; target of P0-C.
- `memory_generate_summary(path=<folder>)` — on-demand `SUMMARY.md` draft generator. Implementation at `core/tools/agent_memory_mcp/tools/read_tools/_generation.py` (lines 60–156). Target of extension in P1-A.
- `memory_read_file(path=<str>)` — file read with 20 KB inline threshold and temp-file fallback. Implementation at `core/tools/agent_memory_mcp/tools/read_tools/_inspection.py` (lines 59–127). Target of P2.
- `memory_stage_external` — external material ingestion. Target of frontmatter autopopulation in P1-B.
- `memory_check_knowledge_freshness` — existing freshness-check tool. Target of `IN/` extension in P1-B.

**Artifact paths.**

- `CLAUDE.md` (repo root) — first file agents read. Target of P0-B.
- `memory/working/projects/SUMMARY.md` — projects navigator. Frontmatter: `type: projects-navigator`, `generated: <date>`, `project_count: <n>`. Regenerated by `memory_generate_summary`, on-demand only today.
- `memory/working/projects/<name>/SUMMARY.md` — per-project briefing. Frontmatter includes `status`, `cognitive_mode`, `current_focus`, `open_questions`, `last_activity`, `origin_session`, `trust`, `source: agent-generated`, `active_plans`. Target of extension in P1-A.
- `memory/working/projects/README.md` — target of creation in P0-B (stub) and P1-C (full lifecycle).
- `memory/working/projects/<name>/IN/` — staged external material. Target of frontmatter work in P1-B.
- `memory/working/projects/<name>/OUT/` — emitted artifacts scoped to the project.
- `memory/working/projects/<name>/plans/` — YAML plans managed by `memory_plan_*` tools.
- `memory/working/projects/<name>/questions.md` — open questions.
- `memory/working/projects/<name>/operations.jsonl` — append-only operations audit.

**Infrastructure already in place (don't rebuild).**

- `record_trace` in `core/tools/agent_memory_mcp/plan_trace.py` — span-based timing infrastructure. Reuse for P0-A step 1 instrumentation.
- `memory_session_health_check` — surface for runtime diagnostics. Extend with context_project timings in P0-A.
- `guard_pipeline.py` — existing ms-level timing pattern. Reference for P0-A instrumentation style.
- Frontmatter schema conventions under `core/governance/` — extend rather than create new schema location for P1-B.

**Ordering one-liner.** Ship in this order for the smoothest dependency graph: P0-A step 1 (instrumentation) → P0-C → P0-A steps 2–7 → P0-B → P1-C → P1-A → P1-B → P2. Anything in P1 or P2 can parallelize across contributors once P0 is in.
