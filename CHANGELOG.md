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
