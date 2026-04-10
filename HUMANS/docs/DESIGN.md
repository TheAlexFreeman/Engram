# Engram: Design Philosophy and Future Directions

A companion document for humans exploring this project — covering the architectural principles behind the system, its intended and emergent use cases, natural directions for future development, and integration possibilities with external tools and platforms.

---

## Part I: Design Philosophy

> The theological and philosophical foundations for these design principles are developed at length in [FIATLUX.md](../../FIATLUX.md) — the system's ultimate authority document. This section covers the practical design philosophy; FIATLUX.md grounds it in a broader account of language, technology, and human authority.

### The core premise

Every AI conversation starts from zero. Models have no persistent state between sessions — no memory of who you are, what you've told them, or what you've built together. This forces users into a repetitive cycle: re-explain context, re-state preferences, re-teach workflows. The more capable the model, the more painful this reset becomes, because the gap between what the model *could* do with context and what it *actually* does without it grows wider with each generation.

Engram solves this by externalizing memory into a structured, version-controlled repository that any model can read. The key insight is that **memory is data, not state** — it belongs in files the user owns, not in a platform's opaque context window or fine-tuning parameters.

### Design principles

**1. Files over APIs.** The entire system is markdown files in a git repository. No database, no cloud service, no proprietary format. This makes the memory human-readable, human-editable, machine-portable, diffable, and backed by decades of tooling for versioning, merging, and auditing. A user can open any file, read what the agent "knows," and change it with a text editor.

**2. Model-agnostic by construction.** The memory system doesn't depend on any model's capabilities, context window size, or tool-use abilities. It works with Claude, GPT, Gemini, Llama, or any future model that can read text files. The bootstrap sequence in README.md is written as instructions any competent model can follow. Platform-specific adapters (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) are thin pointers to the canonical source of truth, not duplicated rule sets. The machine-readable `agent-bootstrap.toml` mirrors the routing logic in `core/INIT.md` with token budgets and per-step metadata, giving tool-use-capable agents a structured alternative to parsing markdown.

**3. Progressive disclosure.** The system has significant depth — trust-weighted retrieval, instruction containment, temporal decay, maturity-adaptive thresholds, emergent categorization, and a large MCP tool surface split across three tiers — but none of this complexity is visible to a new user. Setup offers a browser-based wizard or a shell script with eight starter profiles. The first session is a four-phase collaborative conversation: the agent does real work with the user on a seed task, demonstrates capabilities inline, discovers the user's working style through observation, and confirms a profile at the end. The governance layer operates silently. The MCP tool surface is invisible unless the user looks. Complexity reveals itself only as the system matures and the user engages more deeply.

**4. The user owns the truth.** Every piece of memory has provenance metadata tracking where it came from, when it was last verified, and how much to trust it. The user can inspect, edit, revert, or delete anything at any time. Git provides a complete audit trail. The system never writes to protected files without explicit approval. The browser dashboard and viewers let users see their memory without starting an AI session. This is a fundamental architectural commitment: the human is always the authority, and the system must make its state transparent enough for the human to exercise that authority.

**5. Security as architecture, not policy.** Defense against memory injection (the risk that an adversary plants content the agent later acts on as legitimate) is built into the system's structure, not bolted on as guidelines. External content is quarantined by default. Trust levels are enforced structurally — through the MCP path-policy layer. Instruction containment is a folder-level contract. Skills are protected-tier. The belief-diff log makes drift visible. Identity churn tracking rate-limits rapid personality changes. These are structural constraints that remain effective regardless of which model reads the repo or how capable it is at following instructions.

**6. Self-organizing dynamics.** The system doesn't just store memory — it curates it. ACCESS.jsonl tracks what's retrieved and how useful it was. Aggregation identifies patterns. High-value knowledge is amplified; low-value knowledge cools toward retirement. Categories emerge from co-retrieval patterns rather than being imposed upfront. Governance rules themselves are subject to evidence-based revision. The MCP tool surface (`memory_access_analytics`, `memory_run_aggregation`, `memory_check_aggregation_triggers`, `memory_get_maturity_signals`) gives agents programmatic access to these self-organizing dynamics. The system is designed to become more useful over time through its own feedback loops, not just through accumulation.

**7. Graceful degradation.** The system adapts to constraints rather than failing. Read-only platforms get deferred-action summaries. Models with small context windows get compressed summaries. Missing files don't break the bootstrap — the sequence has explicit skip conditions. The validator is optional. Tier 2 write tools are gated behind an environment flag. Every feature is designed so that its absence reduces functionality without breaking the system.

**8. Context efficiency as a first-class concern.** Every governance file, every skill, every protocol competes for space in the agent's context window — and every token spent on governance is a token not spent on the user's actual task. The system manages this budget deliberately: a context loading manifest tells the agent exactly which files to load for each session type (returning sessions cost 3,000–7,000 tokens; full bootstrap costs 18,000–25,000), governance files are split into always-load summaries and on-demand reference documents, and skip annotations prevent redundant reads across files. Context efficiency is not an optimization applied after the fact — it is a design constraint that shapes how every file is written, scoped, and cross-referenced. See "The dual-audience problem" below for a deeper treatment.

### The compression hierarchy

One of the system's most distinctive architectural choices is its approach to information compression. Rather than storing everything at full fidelity or summarizing everything to the same level, the system uses a **progressive compression hierarchy**:

- **Leaf level** (individual chat summaries): moderately detailed. Key topics, decisions, action items.
- **Mid level** (monthly, folder-level): compressed. Major themes, recurring topics, significant decisions.
- **Top level** (yearly, cross-folder): abstract. Broad patterns, evolution of interests, turning points.

This mirrors how human memory works: recent events are vivid and detailed; older events are compressed into narratives and patterns; only the most significant moments from the distant past remain individually accessible. The hierarchy also serves a practical purpose: the agent reads summaries at progressively higher levels to decide what to retrieve in detail, minimizing token usage while maximizing context relevance.

### Format layer vs. runtime layer

The repository treats the memory contract and the MCP server as two distinct layers.

**Format layer.** The modules under `core/tools/agent_memory_mcp/core/` expose the file-format and validation contract without depending on `mcp`. They re-export the canonical implementations in `core/tools/agent_memory_mcp/{errors,frontmatter_utils,git_repo,models,path_policy}.py`, which cover exception types, frontmatter parsing, git subprocess operations, structured write results, and path-policy validation. Human-facing tooling such as validators and setup scripts can import this layer directly.

**Runtime layer.** The MCP server lives in `core/tools/agent_memory_mcp/server.py` and the tool registration modules under `core/tools/agent_memory_mcp/tools/`. This layer requires the `mcp` package and is responsible for exposing the governed read/write surface to agents. It organizes the tool surface into three tiers: Tier 0 (read-only), Tier 1 (semantic operations), and Tier 2 (gated write primitives). See [MCP.md](MCP.md) for the live inventory and full tool reference.

The package root (`engram_mcp.agent_memory_mcp`) is lazy by design: it doesn't import the server until a caller asks for `mcp`, `create_mcp`, or another runtime export. That keeps the boundary structural rather than purely documentary.

### The governed-write model

The MCP layer implements a distinctive approach to memory mutation. Rather than giving agents unrestricted file access, all governed writes follow a **preview → approve → commit** workflow:

1. **Preview.** The agent calls a semantic tool (e.g. `memory_promote_knowledge`, `memory_plan_execute`). The server validates the request against path policies, change categories, and frontmatter rules, then returns a structured preview: the proposed diff, affected files, and commit message.
2. **Approve.** The agent (or user, for protected-tier changes) reviews the preview and decides whether to proceed.
3. **Commit.** The approved change is committed with full provenance metadata, and the response includes publication details (commit SHA, changed files, new state) — eliminating the need for a read-after-write round-trip.

**Version tokens** prevent stale overwrites: each file read returns a token, and writes must pass the token back to confirm the agent is working from current content.

**Change classes** map onto the governance model: automatic changes commit immediately, proposed changes surface for awareness, and protected changes require explicit approval. The MCP server enforces these classifications at the API boundary, making governance structural rather than relying on the agent to follow instructions.

**Tier 2 write primitives** (`memory_write`, `memory_edit`, `memory_delete`, `memory_move`, `memory_commit`) use a staged-transaction model: mutations are staged in git's index without committing, and `memory_commit` seals them as a single atomic commit. These tools are gated behind the `MEMORY_ENABLE_RAW_WRITE_TOOLS` environment flag because they bypass the semantic governance layer — they're a fallback for operations that don't yet have a dedicated semantic tool, not the primary write path.

### Plans as durable work contexts

Most meaningful work spans multiple sessions. Engram's **plan system** treats multi-session projects as first-class persistent objects stored in `core/memory/working/projects/`. A plan is a YAML-structured document with:

- **Phases and tasks** — hierarchical breakdown with status tracking.
- **Execution state** — `status`, `next_action`, phase progress percentages.
- **Task-local sequencing** — plans are the one place outside `skills/` and `governance/` that may contain procedural instructions, scoped to that specific investigation.
- **Sources** — per-phase reading list declaring what the agent should review before acting, along with the intent for each source.
- **Postconditions** — per-phase success criteria (free-text, or typed with `check`/`grep`/`test`/`manual` validators) that declare what must be true after the phase is done.
- **Approval gates** — `requires_approval: true` on a phase tells downstream tooling to pause and surface the gate before writing anything.
- **Execution budget** — a top-level `budget` block with an optional `deadline` (YYYY-MM-DD), `max_sessions` cap, and an `advisory` flag that controls whether the cap is enforced or advisory-only.

Five MCP tools manage the plan lifecycle:

- `memory_plan_create` — create a structured plan with phases and tasks.
- `memory_plan_execute` — advance phases, mark items complete, record failures, update execution state.
- `memory_plan_verify` — evaluate a phase's postconditions without modifying state.
- `memory_plan_review` — review outcomes, finalize or archive.
- `memory_list_plans` — inventory plans in a project.

#### Phase execution cycle

For each phase, the recommended execution cycle is:

1. **`inspect`** — confirm sources, postconditions, approval gate, and budget status before touching anything.
2. **`start`** — transition the phase to `in-progress`; the response includes sources to read and whether approval is required.
3. *(agent reads sources and performs the work)*
4. **`complete`** (with `verify=true`) — evaluate postconditions, then seal the phase with a commit SHA if all pass. If postconditions fail, the phase stays `in-progress` and the response includes `verification_results` so the agent can diagnose and retry.
5. On failure: **`record_failure`** — append a `PhaseFailure` entry (timestamped reason plus optional verification results) to the phase's failure log, then retry from step 3.

The `inspect` and `start` responses both surface `sources`, `postconditions`, `requires_approval`, and `budget_status` so that agents have the full execution context without additional file reads.

#### Single-call context assembly

Phase 8 adds a complementary read path for the plan system: `memory_plan_briefing`. Instead of requiring an agent to chain `inspect`, source-file reads, approval lookup, and trace queries before starting work, the server can now assemble a single briefing packet for the requested phase. The packet composes `phase_payload()` with source excerpts, failure history, recent plan traces, approval state, and explicit context-budget metadata so the agent can trade fidelity against context cost deliberately. This keeps the plan system's write path unchanged while reducing setup overhead on every execution cycle.

#### Inline verification and retry context

Postconditions can be validated automatically via `memory_plan_verify` (read-only) or inline during `complete` (with `verify=true`). Four validator types are supported: `check` (file existence), `grep` (pattern search), `test` (allowlisted shell command, gated behind `ENGRAM_TIER2`), and `manual` (human-evaluated, always skipped by automation).

When a phase fails, the agent records a `PhaseFailure` with `record_failure`. Failure history is surfaced in both `phase_payload()` (as `failures` list and `attempt_number`) and `next_action()` (as `has_prior_failures`, `attempt_number`, and `suggest_revision` when attempts ≥ 3). This gives agents full retry context without re-reading the plan file.

Plans solve a specific problem: without persistent multi-session roadmaps, agents either lose track of complex work between conversations or rely on the user to re-supply the project context every session. With plans, the project's full context — goals, progress, decisions, next steps — is always available.

### The feedback loop

The system's most important property is that it improves through use. The feedback loop operates at multiple scales:

1. **Per-retrieval**: ACCESS.jsonl entries record whether each file retrieval was helpful, creating fine-grained signal. MCP tools (`memory_log_access`, `memory_log_access_batch`) make this programmatic.
2. **Per-aggregation**: Accumulated ACCESS data is analyzed to update summaries, identify high/low-value files, and detect co-retrieval clusters. MCP tools (`memory_run_aggregation`, `memory_check_aggregation_triggers`, `memory_access_analytics`) automate the analysis.
3. **Per-session**: Reflection notes (`memory_record_reflection`) capture how memory influenced the session's quality — a meta-level that pure retrieval tracking can't capture.
4. **Per-review**: Periodic reviews (`memory_run_periodic_review`, `memory_prepare_periodic_review`) assess whether governance rules themselves are producing good outcomes, closing the loop between top-down constraints and bottom-up evidence.

Each scale feeds into the next: retrieval data informs aggregation, aggregation informs summaries, summaries inform retrieval, and the whole system is evaluated during review. This is not a storage system — it's a self-organizing process.

### Maturity as a design concept

The system explicitly models its own developmental stage. A young system (Exploration) uses loose thresholds, captures aggressively, and tolerates ambiguity. A mature system (Consolidation) uses tight thresholds, captures selectively, and enforces order. The transition between stages is driven by quantitative signals (session count, retrieval success rate, confirmation ratio — available via `memory_get_maturity_signals`), not calendar time.

This adaptive approach prevents a common failure mode in knowledge management systems: applying mature-system rules to a young system (creating bureaucratic overhead before there's enough data to justify it) or applying young-system rules to a mature system (allowing unchecked growth in a system that should be consolidating).

### The dual-audience problem

The memory system serves two primary audiences with fundamentally different needs. Human readers want self-contained, readable documents they can understand without cross-referencing six other files. Agent readers want minimal, non-redundant context that maximizes the token budget available for the user's actual task. These goals are in direct tension: what makes a governance file readable for a human (restating key concepts, providing worked examples, explaining rationale) is exactly what wastes an agent's context window through redundancy.

A third audience — visual human readers — emerged with the browser views. The dashboard, knowledge explorer, project viewer, and other views serve people who want to see their memory at a glance rather than reading markdown files. The views consume the same underlying files but present them through interactive panels, graphs, and navigable card layouts.

This three-audience tension is not a problem to solve once — it is a permanent design constraint that every file in the system must navigate. The strategies that have emerged:

**Role classification.** Every file in `core/governance/` falls into one of three roles: *always-load after entry* (read once the agent reaches the live router — must be lean and non-redundant), *on-demand* (loaded only when a specific operation requires it — can be more detailed), or *human-only* (never loaded by agents — can be as expansive as needed). The context loading manifest in `core/INIT.md` makes these roles explicit.

- *Always-load after entry:* `core/INIT.md`. The architectural starting point is `README.md`; once the agent reaches `core/INIT.md`, that file carries the live operational weight of a normal session and must stay lean.
- *On-demand:* `session-checklists.md`, `curation-policy.md`, `content-boundaries.md`, `update-guidelines.md` (loaded on full bootstrap), `curation-algorithms.md` (loaded during aggregation or stage transitions), `system-maturity.md` (loaded during periodic review), `security-signals.md` (loaded during periodic review).
- *Human-only:* `HUMANS/docs/GLOSSARY.md`. Every term it defines is already introduced in context by the governance file that establishes it. It exists for humans browsing the repo, not for agents building context.

**Denormalized lookup files.** `core/INIT.md` is a deliberately denormalized document: it duplicates threshold values, decision guides, and operational parameters from across the governance layer into a single file the agent reads every session. The normative justification for each value lives in the source files (curation-policy, system-maturity), but the agent never needs to load those files just to look up a threshold. This is the database-design principle of trading storage redundancy for read performance, applied to context windows.

**Skip annotations.** When a governance file restates information that already exists in `core/INIT.md` (trust-level behaviors, decay thresholds, anomaly signals), it includes a one-line annotation: *"If you've already loaded core/INIT.md, skip this section."* This preserves readability for humans browsing the file while giving agents an explicit exit ramp from redundant content.

**Checklist-skill separation.** Session checklists (`core/governance/session-checklists.md`) are self-sufficient for normal operation — they include inline quality criteria and anti-patterns. The full skill files (`core/memory/skills/session-start/SKILL.md`, `core/memory/skills/session-wrapup/SKILL.md`) are on-demand references for first bootstrap or uncertainty. This avoids loading ~950 words of skill files every session when a ~600-word checklist covers the same ground.

### Principles for dual-audience friendliness

These principles apply to any file in the system — governance docs, skills, README sections, or future additions:

**Write for the human first, annotate for the agent.** The primary text should be clear and self-contained for a human reader. Agent-specific routing ("skip this if you've loaded X") goes in annotations, not in the main prose. A human skimming the file shouldn't feel like they're reading machine instructions.

**Justify once, reference everywhere.** The rationale for a rule (why this threshold, why this folder contract, why this trust level) should live in exactly one place — typically the governance file that establishes the rule. Every other file that applies the rule should reference that source, not re-derive the justification. This keeps the agent's context budget focused on *what to do*, not *why to do it* for the twentieth time.

**Put operational content at the top, reference content at the bottom.** When an agent loads a file, the first few hundred tokens are the most valuable — they're read before the agent can decide whether the rest is needed. Decision guides, active thresholds, and executable procedures should come before rationale sections, worked examples, and edge-case discussions.

**Make load boundaries explicit.** If a file should only be loaded under certain conditions, say so in the first line — not buried in a section heading or implied by the file's location. The pattern is a bolded header: *"Load this file only when running aggregation or a stage transition."* This costs one line of context and saves potentially thousands of tokens of unnecessary loading.

**Separate stable reference from volatile state.** A file that mixes permanent rules with frequently updated state (dates, thresholds, assessment logs) forces the agent to re-read stable content every time it needs to check the volatile part. The live-router pattern (`core/INIT.md`) — a lean, frequently-updated state file that points to stable reference documents for rationale — keeps the hot path short.

**Measure what you mandate.** Every piece of bookkeeping the system asks the agent to perform (ACCESS logging, reflection notes, helpfulness scoring, aggregation, periodic review) has a cost in context and compliance. Before adding a new requirement, ask: does this feed a feedback loop that measurably improves the system? If the answer is "it might be useful someday," defer it. The system should have the minimum governance that produces the maximum self-organization — not the maximum governance that can be specified.

---

## Part II: Product Use Cases

### Primary: Personal AI memory for individual users

The core use case is an individual who works with AI regularly — a developer, researcher, writer, or knowledge worker — and wants their AI assistant to accumulate understanding of who they are and how they work. The system acts as a persistent identity layer that sits beneath whatever AI tool the user happens to use on any given day.

**Value proposition**: The agent starts every session by reading your profile, preferences, and recent history. By session 3, it knows your coding style. By session 10, it knows which questions to ask and which to skip. By session 50, it has a nuanced model of your thinking patterns, recurring projects, and evolving interests. Switching from Claude to GPT to a local model loses nothing — the memory is in your files, not in any platform's state.

The browser dashboard makes this tangible even outside agent sessions: users can see their knowledge domains, active projects, recent activity, and system health at a glance — all running client-side with no server or data leaving the machine.

### Developer workflow augmentation

Software developers already live in git repositories. Adding a memory repo to their workflow is natural. Specific high-value patterns:

- **Cross-session debugging context.** The agent remembers what you tried yesterday, which hypotheses were eliminated, and which leads were promising. No more re-explaining the problem.
- **Codebase-specific conventions.** Skills files encode project-specific patterns: commit message formats, testing conventions, deployment procedures, architectural decisions. The agent follows your team's norms without being told each time.
- **Onboarding acceleration.** A team could maintain a shared memory repo with project knowledge, architectural decisions, and common procedures. New team members' AI assistants would immediately understand the project context.
- **Long-running project context.** For multi-week or multi-month projects, the plan system maintains structured roadmaps with phases, tasks, and execution state — decisions, pivots, and accumulated knowledge persist across sessions without relying on context windows.

### Research and knowledge management

Researchers accumulate knowledge across many sessions, often on overlapping topics. The memory system's strengths are particularly well-suited:

- **Cross-session synthesis.** Knowledge files persist across sessions, so the agent can connect insights from Tuesday's literature review to Thursday's data analysis without the user manually bridging them.
- **Emergent abstractions.** The system is designed to detect cross-domain patterns and propose meta-knowledge. A researcher working on both statistical methods and experimental design might find the agent surfacing connections neither the agent nor the researcher explicitly taught it.
- **Citation and provenance tracking.** Every piece of ingested knowledge carries provenance metadata. The quarantine zone ensures external research is labeled and segregated until verified. The knowledge graph overlay in the browser views makes citation relationships visual.
- **Living literature reviews.** Knowledge files can serve as evolving summaries of a research area, updated incrementally as new papers or findings are discussed across sessions.

### Team and organizational memory

While designed for individual use, the architecture naturally extends to teams:

- **Shared knowledge bases.** A team repository with knowledge files about the product, architecture, and domain. Every team member's AI assistant reads the same ground truth.
- **Institutional memory preservation.** When team members leave, their accumulated knowledge (architectural decisions, debugging strategies, domain expertise) remains in the repo rather than leaving with them.
- **Onboarding playbooks.** Skills files encoding team-specific workflows (how to deploy, how to review PRs, how to triage bugs) that any team member's AI assistant can follow.

### Education and mentorship

The system's progressive, conversational approach to building a user profile has natural applications in education:

- **Adaptive tutoring.** A student's memory repo tracks what they know, what they're learning, and where they struggle. The AI tutor adjusts difficulty and explanation style across sessions based on accumulated understanding.
- **Long-term mentorship.** A mentor-mentee relationship mediated through AI could use the memory system to maintain continuity across weeks or months, tracking goals, progress, and evolving challenges.
- **Self-directed learning.** A learner exploring a new domain accumulates knowledge files as they go. The system's retrieval patterns reveal which topics they return to (mastery gaps) and which they've moved past.

### Personal productivity and life management

Beyond technical work, the system can serve as a general-purpose persistent AI assistant:

- **Project management.** Tracking multiple projects, deadlines, dependencies, and decisions across sessions. The plan system gives the agent structured multi-session context. The agent remembers what you committed to last week.
- **Writing assistance.** An author's style preferences, character notes, plot decisions, and revision history persist across sessions. The agent maintains consistency across a long writing project.
- **Health and habit tracking.** Preferences, routines, and goals tracked conversationally rather than through rigid forms. The agent adapts its suggestions based on accumulated history.

---

## Part III: Development Trajectory

### Recently realized

These capabilities were future aspirations when the system was first designed. They now exist:

**Pre-commit validation.** The repo includes a pre-commit configuration with Ruff (Python linting and formatting) and `validate_memory_repo.py` (memory-structure and frontmatter validation). Run `pre-commit run --all-files` before pushing.

**Expanded starter profiles.** The browser-based setup wizard (`HUMANS/views/setup.html`) and the shell-based setup script (`HUMANS/setup/setup.sh`) offer eight starter profiles — from Software Developer and Researcher to Student, Creative Writer, and a blank template — covering a broad range of personas.

**Browser-based memory visualization.** Seven standalone HTML pages under `HUMANS/views/`: a seven-panel dashboard (user portrait, system health, active projects, recent activity, knowledge base, scratchpad, skills), a knowledge explorer with canvas-based force-directed knowledge graph, a project viewer with YAML plan timelines and phase indicators, a skills browser, a users browser, a docs viewer, and a trace viewer (`traces.html`) for exploring per-session span timelines. All client-side via the File System Access API.

**Structured observability (TRACES.jsonl).** Every session now emits a `chat-NNN.traces.jsonl` file alongside its summary. Each line is a JSON span with `span_id`, `session_id`, `timestamp`, `span_type` (tool_call, plan_action, retrieval, verification, guardrail_check), `name`, `status` (ok, error, denied), optional `duration_ms`, `metadata`, and `cost`. Span recording is always-on and non-blocking — trace write failures never cause tool errors. The `memory_record_trace` MCP tool allows agents to emit custom spans; `memory_query_traces` supports filtering by session, date, span_type, plan_id, and status with aggregate statistics. Plan actions (create, start, complete, record_failure) and verification runs emit spans automatically. Session summaries include a `metrics:` frontmatter block (tool_calls, plan_actions, retrievals, errors, total_duration_ms, verification counts) when trace data exists. ACCESS.jsonl entries now include `event_type: "retrieval"` to distinguish retrieval events from future tool-call events; curation algorithms filter by this field. Trace files follow the session summary retention lifecycle.

**Structured HITL (approval workflow).** `requires_approval: true` on a plan phase now triggers a full interrupt/resume workflow rather than a bare flag. When `memory_plan_execute` starts a `requires_approval` phase, it automatically creates a YAML approval document in `core/memory/working/approvals/pending/{plan_id}--{phase_id}.yaml`, transitions the plan to `paused`, and returns the approval context. The human reviews via `HUMANS/views/approvals.html` (File System Access API, no server required) or calls `memory_resolve_approval` directly. Approving transitions the plan back to `active`; rejecting transitions it to `blocked`. Expired approvals (default 7-day window) are detected lazily on read and moved to `resolved/` with status `expired`. A `paused` plan status was added to `PLAN_STATUSES` to express "waiting for human input" separately from `blocked` (technical dependency). The approval UI shows pending approvals with expiry countdowns, approve/reject buttons with comment fields, and a resolved history. `SUMMARY.md` under `working/approvals/` is regenerated after every operation. `memory_request_approval` and `memory_resolve_approval` are the explicit MCP tools; the auto-create path makes manual calls optional.

**External tool registry.** `core/memory/skills/tool-registry/` stores YAML-based tool definitions grouped by provider (`shell.yaml`, `api.yaml`, `mcp-external.yaml`). Each definition captures `name` (slug), `description`, `approval_required`, `cost_tier` (free/low/medium/high), `timeout_seconds`, optional `rate_limit`, `tags`, `schema` (JSON Schema for inputs), and `notes`. Engram does not execute external tools — it stores metadata so agents and orchestrators can consult policies before invoking them. The `memory_register_tool` MCP tool creates or updates definitions; `memory_get_tool_policy` queries by name, provider, tags, or cost tier. `phase_payload()` now includes a `tool_policies` field that auto-resolves registry entries matching `test`-type postcondition targets (e.g. a postcondition targeting `"pre-commit run --all-files"` surfaces the `pre-commit-run` policy). SUMMARY.md is regenerated after every registration. The registry ships with seed entries for `pre-commit-run`, `pytest-run`, and `ruff-check`.

**MCP health and analytics tools.** `memory_session_health_check` (session-start maintenance status), `memory_validate` (system integrity check), `memory_get_maturity_signals` (maturity indicators), `memory_access_analytics` (retrieval metrics), `memory_check_knowledge_freshness` (staleness detection), and `memory_audit_trust` (trust decay audit) provide programmatic system health reporting.

**Collaborative onboarding.** The first session is no longer an interview-style intake. The four-phase onboarding flow (`core/memory/skills/onboarding/SKILL.md`) has the agent work with the user on a real seed task, demonstrate capabilities inline, perform a discovery audit of working style, and confirm a profile at the end — with a read-only export path for platforms without write access.

**Knowledge graph analysis.** MCP tools for computing structural metrics (`memory_analyze_graph`) and pruning redundant cross-references (`memory_prune_redundant_links`); plus a browser-based canvas graph overlay with domain coloring, zoom, search, and network analysis.

**Git hooks.** Pre-commit hooks validate frontmatter, check ACCESS.jsonl format, and enforce Python linting/formatting. Protected-tier enforcement (CHANGELOG entries for skills/governance changes) is handled by the MCP governance layer.

### Near-term (next iteration)

**Automated belief-diff generation.** The `core/governance/belief-diff-log.md` protocol is currently manual. A scheduled script (or a GitHub Action on a 30-day cron) could generate the belief diff automatically, making drift detection passive rather than requiring agent initiative.

**Import/export tooling.** The system needs tools for:
- Exporting a complete memory snapshot (for backup or migration).
- Importing memory from other formats (plain text notes, structured databases, other agent memory systems).
- Partial export (sharing knowledge files without identity data, for team contexts).

**Context budget monitoring.** The system tracks retrieval helpfulness but not context cost. A lightweight mechanism — logging approximate token counts consumed by governance files at session start, or tracking how much of the context window is spent on system overhead vs. user work — would provide the data needed to evaluate whether governance files are earning their context budget. This would close the feedback loop on context efficiency the same way ACCESS.jsonl closes the feedback loop on retrieval quality.

**CLI tool.** A dedicated CLI (`engram` or `memory`) wrapping common operations:
- `engram status` — show system health, maturity stage, pending items.
- `engram search <query>` — search across all files using the summary hierarchy.
- `engram import <file>` — import external content to quarantine.
- `engram review` — interactive review of pending queue items.
- `engram export --format <obsidian|notion|plain>` — export for other tools.
- `engram validate` — run the validator with formatted output.

### Medium-term (architectural extensions)

**Multi-user support.** The current architecture assumes a single user. Supporting multiple users (e.g., a team repo) would require:
- Per-user identity folders (or a shared identity with user-specific overlays).
- Access control on identity files (Alice's preferences shouldn't be writable by Bob's agent).
- Conflict resolution for concurrent writes to shared knowledge.
- Git branch strategies for isolated experimentation vs. shared ground truth.

**Semantic retrieval — recently realized.** The `memory_semantic_search` tool provides vector-based semantic search using a local `all-MiniLM-L6-v2` embedding model with a SQLite-backed index (`.engram/search.db`, gitignored). It combines vector similarity, BM25 keyword scoring, temporal freshness, and ACCESS.jsonl helpfulness into a hybrid ranked result set. The embedding index is supplementary to SUMMARY-based navigation and full-text `memory_search`, not a replacement. Requires the optional `search` dependency group (`pip install agent-memory-mcp[search]`).

**Real-time sync.** For users who switch between platforms within a single working session (e.g., Claude Code for coding, ChatGPT for brainstorming), the current per-session architecture means one platform's changes aren't visible to the other until the session ends. A lightweight sync mechanism (filesystem watcher + auto-commit, or a shared working directory) would enable mid-session handoffs.

**Skill marketplace.** Once multiple users have mature memory systems, commonly useful skills become shareable. A skill marketplace (a curated repository of skill files) would allow users to install pre-built workflows. The protected-tier security model already handles this: installed skills would arrive at `trust: low` and require user review before execution, the same way external knowledge is quarantined.

**VS Code / IDE extension.** A lightweight extension that:
- Shows the current user profile in a sidebar panel.
- Provides a "Memory Search" command leveraging the MCP tool surface.
- Highlights when a file being edited is referenced in the memory system.
- Displays the current maturity stage and system health.
- Surfaces pending review-queue items as IDE notifications.

### Long-term (ecosystem evolution)

**Federated memory.** A protocol for memory systems to share knowledge selectively — e.g., a team's shared knowledge repo that individual memory systems can subscribe to, receiving updates to knowledge files while maintaining their own identity and skills. This extends the git model naturally: shared knowledge is a remote repository; individual memory is a local fork.

**Agent-to-agent memory transfer.** When a user has multiple specialized agents (a coding agent, a research agent, a writing agent), they currently share a single memory repo. A more sophisticated architecture would allow agents to maintain separate working memories while sharing a common long-term memory layer — similar to how human working memory is task-specific but draws on shared long-term memory.

**Temporal reasoning.** The system currently stores memory with timestamps but doesn't reason temporally in sophisticated ways. Future extensions could support:
- Automatic detection of time-dependent knowledge ("this API version is current as of March 2026" becoming stale).
- Predictive retrieval based on temporal patterns ("the user usually asks about deployment on Fridays").
- Narrative generation from the temporal stream ("here's how your understanding of distributed systems evolved over the past year").

**Self-modifying governance.** The governance feedback mechanism already allows the agent to propose governance changes based on evidence. The long-term direction is a system where governance rules genuinely co-evolve with content — where thresholds, trust policies, and even folder structures adapt continuously rather than in discrete periodic reviews.

---

## Part IV: Third-Party Integration Possibilities

### Platform integrations

**MCP (Model Context Protocol) server.** The memory repo is exposed as an MCP server for MCP-capable clients such as Claude Code, Codex, Cursor, and IDE integrations. The server provides a governed tool surface across three tiers:

- **Tier 0 — Read-only.** File reading with parsed frontmatter and version tokens, full-text search, reference discovery, link validation, graph analysis, access analytics, session health checks, maturity signal assessment, aggregation trigger monitoring, diff/log inspection, and capability introspection.
- **Tier 1 — Semantic operations.** Knowledge promotion, demotion, and archival with governed previews. Plan creation, execution, and review. Session recording, chat summaries, reflection notes. Access logging (single and batch). Aggregation orchestration. Periodic review execution. Skill and user trait updates with rate-limiting. Scratchpad management. Commit revert with preview-first flow.
- **Tier 2 — Write primitives (gated).** Low-level staged mutations such as `memory_write`, `memory_edit`, `memory_delete`, `memory_move`, `memory_update_frontmatter`, and `memory_update_frontmatter_bulk`, sealed by `memory_commit`. Available only when `MEMORY_ENABLE_RAW_WRITE_TOOLS=true`.

The server also exposes **MCP resources** (`memory://session/health`, `memory://plans/active`) and **MCP prompts** (unverified review, promotion preview, periodic review, session wrap-up) for workflow orchestration.

See [MCP.md](MCP.md) for the full human-facing guide to the tool surface.

**GitHub App.** A GitHub App that:
- Runs validation on every push (CI validation).
- Generates belief diffs on a schedule (automated drift detection).
- Auto-archives expired low-trust content (temporal decay enforcement).
- Notifies the user of pending review items via GitHub Issues or PR comments.

### AI platform integrations

**Claude Projects.** Claude Projects already supports uploading files as project knowledge. A sync tool that packages the most relevant subset of the memory repo (identity, recent knowledge, active skills) into a Claude Project would give Claude persistent context without manual file uploads. The tool would respect the compression hierarchy, uploading summaries rather than full files where appropriate.

**Custom GPTs.** A builder tool that converts the memory repo into a Custom GPT configuration: identity files become the GPT's instructions, knowledge files become its uploaded knowledge base, skills become its behavioral guidelines. The tool would handle the translation between the repo's markdown format and OpenAI's configuration schema.

**LangChain / LangGraph / CrewAI.** The memory repo could serve as a shared state layer for multi-agent frameworks. Each agent in a LangGraph workflow could read from the memory repo for user context and write observations back. The trust system would naturally differentiate between user-provided context (high trust) and agent-generated observations (medium trust).

### Data integrations

**Obsidian sync.** Many knowledge workers already maintain Obsidian vaults. A bidirectional sync tool could:
- Import relevant Obsidian notes into `core/memory/knowledge/` (with `source: external-research`, landing in `_unverified/`).
- Export knowledge files back to Obsidian for the user's personal reference.
- Map Obsidian's tag system to the memory repo's emergent categorization.

**Notion / Linear / Jira.** Project management tools contain context that enriches the memory system. Integrations could:
- Import active project context (current sprint, assigned tickets, project goals) as knowledge files.
- Export the agent's session summaries as Notion pages or Linear comments.
- Sync task status bidirectionally so the agent knows what the user is working on.

**Calendar and communication.** Integrations with calendar (meeting context), email (stakeholder communication patterns), and Slack (team dynamics) would enrich the identity and knowledge layers with context the user would otherwise need to re-explain each session. All such content would flow through the quarantine zone.

---

## Part V: Run State and Resumability

Long-horizon plan execution depends on reliable state persistence across sessions. The deep research report's strongest recommendation: "Run state is for correctness and resumability; memory is for recall and personalization. Mixing them tends to cause state drift."

Engram addresses this through a dedicated **RunState** layer that separates execution state from plan definitions:

**Separation of concerns.** Plan YAML files define *what* needs to happen (phases, sources, changes, postconditions). RunState JSON files track *where execution is* (current task position, intermediate outputs, error context, resumption hints). Plan YAML remains authoritative for phase status; run state is additive.

**Persistence model.** Run state is persisted as a JSON file alongside each plan YAML (`{plan_id}.run-state.json`). It is auto-saved after every `memory_plan_execute` action (start, complete, record_failure) for crash recovery, and git-committed at phase boundaries for durability.

**Resumption.** The `memory_plan_resume` MCP tool provides single-call resumption: it loads run state, validates it against the plan, detects session staleness, and assembles a minimal restart context including intermediate outputs and a phase briefing. When no run state exists, it degrades gracefully to plan-only context.

**Context integration.** The `assemble_briefing()` system automatically includes run state data (current task, next action hint, error context, intermediate outputs) when available, accounting for it in the context budget.

**Concurrency.** Last-writer-wins with a 60-minute staleness warning. No file locking, consistent with Engram's git-based patterns.

**Pruning.** Run state files are capped at 50 KB. Completed phase entries are summarized when the limit approaches; active phases are never pruned.

## Part VI: Tool Policy Enforcement

The tool registry (Phase 4) stores metadata about external tools — approval requirements, cost tiers, rate limits — but these were informational only. Phase 11 makes them enforceable at runtime.

**`check_tool_policy()`.** A pure read function that evaluates a tool's registered policies and returns a `PolicyCheckResult` with `allowed`, `reason`, `required_action`, and `violation_type`. Callers decide how to act on the result.

**Enforcement tiers.** Two levels of enforcement:
- *Hard blocks* for `approval_required` (tool must be approved through the approval workflow) and `rate_limit` exceeded (sliding window counted from trace spans). The tool cannot proceed.
- *Soft warnings* for `cost_tier="high"` when plan budget is tight. The tool proceeds but the caller is informed.

**Rate limits.** Parsed from the `rate_limit` field as `"N/period"` (e.g., `"10/hour"`, `"5/day"`). Counts use existing trace spans (`tool_call` type) as the timestamp source — no new storage needed. Sliding window: `minute` (60s), `hour` (3600s), `day` (86400s), or `session` (same session_id).

**Integration.** Policy checks are wired into `verify_postconditions()` for test-type postconditions. When a postcondition command matches a registered tool, its policy is checked before execution. Violations produce `policy_violation` trace spans for observability. `ENGRAM_EVAL_MODE=1` bypasses all policy checks for eval scenarios.

**Fail-open.** Unregistered tools (no policy in the registry) are always allowed. Policy enforcement is additive — it only gates tools that have explicit policies defined.

## Part VII: Runtime Guard Pipeline

The guard pipeline (`guard_pipeline.py`) provides a centralized, extensible pre-write validation layer. It implements the deep research report's recommendation for guardrails as a "parallel control plane" — cheap checks that run before expensive operations.

**Architecture.** A `Guard` abstract base class defines a single `check(context) -> GuardResult` method. A `GuardPipeline` executes guards in order, accumulating warnings and short-circuiting on the first `block` or `require_approval` result. `GuardContext` carries the write target path, content, operation type, and metadata. `PipelineResult` aggregates all results with timing.

**Built-in guards (in execution order):**
1. **PathGuard** — wraps existing `path_policy.py` directory protection (protected roots, raw mutation roots)
2. **ContentSizeGuard** — blocks files exceeding 100 KB (configurable via `ENGRAM_MAX_FILE_SIZE`)
3. **FrontmatterGuard** — validates YAML frontmatter schema on markdown writes (source enum, trust enum, recommended fields)
4. **TrustBoundaryGuard** — requires approval when `trust:high` is assigned by an agent (source is not `user-stated`)

**Result types.** `pass` (no issue), `warn` (proceed but inform), `block` (hard stop), `require_approval` (needs human confirmation). Warnings accumulate across guards; blocks short-circuit the pipeline.

**Observability.** Every pipeline run emits a `guardrail_check` trace span with guard count, block source, and accumulated warnings.

**Extensibility.** New guards are added by subclassing `Guard` and registering in the pipeline. `default_pipeline()` builds the standard guard set; callers can customize the guard list.

## Part VIII: Eval Hardening

Phase 7 delivered the eval framework (schema, runner, metrics, MCP tools). Phase 13 hardens it for production use.

**Isolated execution.** `run_scenario()` accepts `isolated=True` to execute in a fresh temporary directory. `run_suite()` already isolates each scenario. Artifacts never persist in the main repo.

**CI integration.** `test_eval_scenarios.py` discovers all YAML scenarios in `memory/skills/eval-scenarios/` and runs each as a parameterized pytest case. `pytest -m eval` runs eval scenarios separately from unit tests.

**Result history.** `append_eval_history()` persists scenario results to `eval-history.jsonl`. `load_eval_history()` reads them back for trend analysis.

**Regression detection.** `compare_eval_runs()` compares two result sets. Status regressions (pass to fail) are hard failures. Metric degradation beyond 10% triggers warnings. This enables CI pipelines to catch regressions before merge.

**Expanded scenarios.** Nine scenarios covering: basic lifecycle, approval workflows, verification retries, trace recording, tool policy integration, run state checkpoint/resume, run state failure recovery, guard pipeline blocking, and policy enforcement.

## Part IX: Trace Enrichment

Phase 3 delivered structured traces with `TraceSpan`, `TRACES.jsonl`, and querying. Phase 14 fills in the operational metrics gaps.

**Cost tracking.** `estimate_cost()` converts character counts to approximate token counts (4 chars/token default). Plan execution traces (`start`, `complete`, `record_failure`) now include `cost: {tokens_in, tokens_out}`. `memory_query_traces` aggregates include `total_cost` with summed token counts.

**Parent-child spans.** `record_trace()` returns a `span_id` that can be passed as `parent_span_id` to child operations, enabling call-tree reconstruction. The plan `start` action returns its span ID for downstream use.

**Aggregate metrics.** `memory_query_traces` response now includes `total_cost` in its `aggregates` block alongside `total_duration_ms`, `by_type`, `by_status`, and `error_rate`.

---

## Summary

Engram is a system built on the conviction that AI memory should be a user-owned, human-readable, model-portable artifact — not a platform feature that locks users in or an opaque embedding store that defies inspection. Its architecture draws from version control (git as the audit trail), information retrieval (progressive compression and trust-weighted retrieval), immune systems (quarantine, decay, anomaly detection), and developmental biology (maturity stages with adaptive parameters).

The system serves three audiences — humans who read and edit the files, agents who load them into finite context windows, and visual users who browse them through the dashboard and viewers — and treats the tension between their needs as a permanent design constraint rather than a problem to solve once. Context efficiency is not an afterthought but a first-class architectural concern, shaping how files are scoped, split, annotated, and loaded.

The system's value grows with use: each session adds signal, each aggregation sharpens retrieval, each review strengthens governance. The MCP tool surface makes these feedback loops programmatic rather than manual. The future directions outlined here extend that trajectory: from individual to team, from manual to automated, from single-platform to ecosystem-wide. But the core principle remains constant: **memory is yours, stored in files you control, in a format any model can read.**
