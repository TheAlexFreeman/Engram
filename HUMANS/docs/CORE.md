# Core Concepts

This document explains Engram at the "why it is built this way" level.

- If you want to start using it, read [QUICKSTART.md](QUICKSTART.md).
- If you want deeper theory and future directions, read [DESIGN.md](DESIGN.md).
- If you want the MCP tool surface explained, read [MCP.md](MCP.md).
- If you want troubleshooting help, read [HELP.md](HELP.md).
- If you want terminology help, read [GLOSSARY.md](GLOSSARY.md).

## In plain language

Engram is a durable memory layer for AI agents.

Instead of relying on a model to remember past conversations on its own, the important context lives in normal files that both humans and agents can inspect. That makes memory portable across tools, reviewable over time, and easier to correct when it drifts.

If you are nontechnical, a good mental model is: this is a shared notebook plus filing system plus change log for your AI — with a browser dashboard so you can see what it knows without starting a conversation.

If you are technical, a good mental model is: this is a git-backed, model-agnostic memory architecture with an MCP tool surface, explicit routing, retrieval feedback, trust metadata, governed writes with preview workflows, and human-controlled updates.

## What problem this system is solving

Most AI systems are stateless or platform-bound:

- A model may forget important context between sessions.
- A memory feature may only work inside one product.
- It may be hard to see what the system "knows" or how that knowledge changed.
- Bad information can quietly accumulate because memory is opaque.

Engram addresses those problems by making memory:

- **Portable:** the memory is in ordinary files, not hidden inside a vendor-specific feature. Any model that can read text files can use it.
- **Inspectable:** you can read, edit, diff, and audit what is stored — through a text editor, git history, or the browser dashboard and viewers.
- **Governed:** the system has explicit rules for what may change and how. Writes go through a preview/approve workflow. Changes are classified as automatic, proposed, or protected.
- **Adaptive:** retrieval logs and access analytics feed back into how the memory is organized. High-value content is amplified; low-value content decays.

## Fundamental design decisions

### 1. Memory is stored in a git repository

This is the most important architectural decision.

Why:

- Files are durable and easy to back up.
- Git gives history, diffs, reversibility, and accountability.
- Any capable model can work with the same memory if it can read the repo.
- Humans are not locked into a single platform or vendor.

Tradeoff:

- This is less automatic than a hidden built-in memory feature.
- Users or agents sometimes need to maintain summaries, logs, and structure explicitly.

The system accepts that tradeoff because transparency and portability are more important than invisible convenience.

### 2. Routing is separate from reference material

The live operational router is [core/INIT.md](../../core/INIT.md).

That file tells an agent what to load for the current kind of session. It defines five **session modes** — first run, returning, full bootstrap, periodic review, and automation — each with its own context loading manifest. It is intentionally compact because most sessions follow the returning path, which loads only the essentials.

The session entry point for returning sessions is [core/memory/HOME.md](../../core/memory/HOME.md), which provides the loading order: user portrait → activity summary → scratchpad files → task-driven drill-downs.

Other files have different roles:

- [README.md](../../README.md): architecture and protocol reference (the canonical agent-facing contract).
- [agent-bootstrap.toml](../../agent-bootstrap.toml): machine-readable mirror of the routing logic, with token budgets and per-step metadata.
- `core/governance/`: governance and operational rules for agents.
- `HUMANS/`: explanation, setup, views, and tooling for people — never loaded by agents.

This separation is deliberate. It prevents the common failure mode where every important rule is repeated everywhere and drifts out of sync.

### 3. Context should be loaded progressively, not all at once

The system is designed around context efficiency.

Agents should not read the whole repo every session. They should start with summaries and routing files, then load additional detail only when the task justifies it. The compact returning path typically costs 3,000–7,000 tokens; a full bootstrap costs 18,000–25,000.

Why:

- Context windows are limited.
- Most tasks do not need all historical detail.
- Smaller, cleaner context usually improves speed and response quality.

That is why the system uses:

- Summary files at many levels, following a progressive compression hierarchy (detailed at the leaf, abstract at the top).
- A compact returning path that loads only `HOME.md` and the summaries it points to.
- On-demand runbooks for detailed procedures (governance docs, skill files).
- Metadata-first checks before loading heavier material.

### 4. Memory is curated, not merely accumulated

This system is not a dumping ground for every past interaction.

It treats memory as something that should become more useful over time. Files are summarized, retrieved selectively, logged in `ACCESS.jsonl`, reviewed for usefulness, and sometimes archived or promoted. The MCP tool surface provides programmatic access to this curation lifecycle — aggregation tools analyze patterns, analytics tools surface high- and low-value content, and promotion/demotion tools move files through trust levels.

Why:

- More data is not the same as better memory.
- Uncurated memory becomes noisy, expensive, and misleading.
- Retrieval patterns reveal what the system actually uses, not just what exists.

The underlying philosophy is that memory quality matters more than memory volume. The access-tracking system (`ACCESS.jsonl` for high-signal events, `ACCESS_SCANS.jsonl` for low-signal overflow) gives the system the data it needs to make these quality judgments.

### 5. Knowledge and instructions are kept separate

Not every file is allowed to tell an agent what to do.

The system distinguishes between:

- **Informational memory:** identity, knowledge, plans, chats.
- **Procedural authority:** `core/memory/skills/`, `core/governance/`, and task-local sequencing inside the currently relevant plan in `core/memory/working/projects/`.

This matters for safety. A knowledge file might contain useful facts, but it should not be able to smuggle in behavioral instructions that quietly change how the agent operates.

That separation — called **instruction containment** — is one of the main defenses against memory injection and slow behavioral drift. See [GLOSSARY.md](GLOSSARY.md) for the full definition.

### 6. Trust and provenance are explicit

Files carry YAML frontmatter describing where information came from (`source`), when it was created, whether it has been verified (`last_verified`), and how much the system should trust it (`trust: high / medium / low`).

Why:

- Not all memory is equally reliable.
- A useful system must distinguish user-confirmed truth from inferred patterns and external research.
- Maintenance decisions (decay, promotion, retirement) depend on knowing how old and how verified content is.

This is why external material goes to `core/memory/knowledge/_unverified/` (the quarantine zone) first instead of becoming trusted memory automatically. Promotion requires user review.

### 7. Humans stay in control of system-level changes

The system is adaptive, but it is not meant to rewrite its own rules without oversight.

Changes follow a three-tier model:

- **Automatic:** ACCESS logs, chat transcripts, routine progress updates — no approval needed.
- **Proposed:** New knowledge files, user profile updates, plan creation — the agent surfaces these for user awareness.
- **Protected:** Skills, governance rules, README — require explicit user approval plus a CHANGELOG entry.

Why:

- The most dangerous errors are often changes to the rules, not the facts.
- Users need to understand why the system behaves differently over time.
- Reviewability matters more than maximum automation when the system is modifying itself.

The MCP tool surface enforces these categories structurally: governed write tools produce previews before committing, and protected-tier changes are flagged for approval.

### 8. The architecture is designed to survive model changes

The repo is the continuity layer, not the model.

The user should be able to switch from one AI platform or model to another without losing the system's working memory, operating rules, and historical context.

This is why the repo uses plain files, platform adapters (thin pointer files like `AGENTS.md` and `CLAUDE.md` that redirect to the canonical contract), human-readable documentation, and a model-agnostic startup contract.

### 9. The MCP layer provides governed tool access

Agents interact with Engram through a **Model Context Protocol (MCP)** server that exposes a governed tool surface organized into three tiers. See [MCP.md](MCP.md) for the live inventory and current counts:

- **Tier 0 (read-only):** Search, analytics, validation, session health, graph analysis, git diagnostics, and file reading. Always available.
- **Tier 1 (semantic operations):** Governed actions for plan management, knowledge lifecycle, session recording, access logging and aggregation, semantic search, graph analysis, periodic review, and skill/user/identity updates. Always available.
- **Tier 2 (write primitives):** Low-level staged file mutations such as `memory_write`, `memory_edit`, `memory_delete`, `memory_move`, `memory_commit`, and frontmatter updates. Gated behind the `MEMORY_ENABLE_RAW_WRITE_TOOLS` environment flag.

Why a tool layer instead of direct file access:

- The MCP server enforces governance rules (change categories, path policies, frontmatter validation) at the API boundary.
- **Governed previews** let agents and users review proposed changes before committing.
- **Version tokens** prevent stale overwrites from concurrent modifications.
- Results include publication metadata (commit SHA, changed files, new state) that eliminate read-after-write round-trips.

The implementation is split into a **format layer** (imports without the MCP runtime — for validators, setup scripts, human tooling) and a **runtime layer** (requires the `mcp` package — the actual server). See [MCP.md](MCP.md) for the full tool reference; see [DESIGN.md](DESIGN.md) for the design rationale.

### 10. Browser views make memory visible without an agent

A suite of standalone HTML pages under `HUMANS/views/` lets users inspect their memory repo in a web browser — no server, no data leaves the machine. Everything runs client-side using the **File System Access API** (Chrome, Edge, Brave, Arc).

The views include:

- **Dashboard:** Seven-panel overview of user portrait, system health, active projects, recent activity, knowledge base, scratchpad, and skills.
- **Knowledge explorer:** Domain picker, file sidebar, frontmatter metadata, markdown rendering with KaTeX math, cross-reference navigation, and a canvas-based knowledge graph overlay.
- **Project viewer:** Card list, detail view with metadata, YAML plan timeline, phase indicators, inline notes.
- **Skills browser, users browser, docs viewer.**

Why:

- Users should be able to see what their memory contains without starting an AI session.
- A visual overview makes the system's self-organizing dynamics tangible — you can see what's growing, what's stale, and how the knowledge structure evolves.
- The browser views serve as a third-audience solution to the dual-audience problem (human readers vs. agent readers) documented in [DESIGN.md](DESIGN.md).

### 11. Plans are first-class persistent objects

Multi-session work is tracked through **plans** stored in `core/memory/working/projects/`. Plans are YAML-structured documents with phases, tasks, execution state (`status`, `next_action`), and task-local sequencing.

Why plans deserve architectural status:

- Most meaningful work spans multiple sessions. Without persistent plans, agents lose track of multi-step projects between conversations.
- Plans are the one place outside `skills/` and `governance/` that may contain task-local procedural instructions (for that specific investigation only).
- MCP plan tools (`memory_plan_create`, `memory_plan_execute`, `memory_plan_review`, `memory_list_plans`) give agents a structured interface for creating, advancing, and completing plans.

### 12. Scratchpads bridge sessions

The `core/memory/working/` area provides a staging layer between ephemeral session context and formal governed memory:

- **USER.md:** The user's channel to the agent. Current priorities, temporary constraints, direct instructions. Trust: high. Author: user only.
- **CURRENT.md:** The agent's working notes. Provisional observations, draft abstractions, cross-session hypotheses. Trust: medium. Author: agent only.
- **notes/:** Dated working files for longer-form drafts.

The scratchpad operates below the governance layer — no frontmatter, no approval requirements, no CHANGELOG entries. Content is either promoted to formal memory when it earns it (the **three-session rule:** "Would this still matter in three sessions?") or cleared when it doesn't.

## Architectural principles

These are the principles that should shape future changes to the system.

### Consistency

Operational router, README, setup flows, validators, MCP tool surface, browser views, and human docs should not tell different stories. If the contract changes, dependent surfaces should be updated together.

Consistency matters because users and agents both rely on the same system. A "mostly right" rule set is still a broken architecture if different files imply different behavior.

### User-friendliness

The system should remain understandable and workable for normal people, not just for maintainers who already know it well.

That means:

- setup should be straightforward (a browser-based wizard or shell script with 8 starter profiles),
- docs should explain the why as well as the how,
- the file structure should stay legible,
- the browser dashboard should give a clear picture without expertise,
- maintenance should prefer practical workflows over clever but fragile ones.

In this project, usability is not cosmetic polish. It is an architectural requirement.

### Context efficiency

The system should preserve a compact normal operating mode.

That means:

- summaries before deep reads,
- on-demand references before unconditional loading,
- small live routing files instead of giant startup prompts,
- careful attention to what each additional file costs in real sessions.

The goal is not minimalism for its own sake. The goal is to make the right context available at the right time without turning every session into a full bootstrap.

### Transparency and reversibility

A good memory system should make it easy to answer:

- What changed?
- Why did it change?
- Who approved it?
- Can we undo it?

Git history, changelog entries, governed preview workflows, and file-based storage make those questions answerable. The MCP server even provides a `memory_revert_commit` tool for undoing changes programmatically.

### Safety through containment

The system assumes memory can become dangerous if it is allowed to act like unreviewed instruction.

That is why it uses:

- trust levels with behavioral rules (high/medium/low),
- quarantine for external material,
- instruction containment (only skills and governance may instruct),
- protected change surfaces with approval requirements,
- temporal decay for unverified content,
- periodic review and anomaly detection,
- belief-diff auditing for slow-burn drift.

The design does not aim to remove all risk. It aims to make risk visible, bounded, and recoverable.

## Guiding philosophy

At a high level, Engram follows a few broad beliefs. For the comprehensive philosophical and theological grounding of these principles — why language is a creative act, why human consent is structurally central, why self-organizing dynamics require governance — see [FIATLUX.md](../../FIATLUX.md).

### Continuity is more valuable than novelty

A good long-term agent should feel like it remembers the user, their work, and prior decisions. That continuity usually matters more than squeezing out one extra clever response in a single isolated session.

### Explicit structure beats hidden magic

Many AI systems promise convenience by hiding how memory works. This project makes the opposite bet: memory should be inspectable, understandable, and governable even if that means a bit more structure.

### The system should improve through use

Usage data should help the memory become better organized over time. The architecture is meant to learn from retrieval patterns, not stay static forever. Access analytics, aggregation, knowledge amplification, and emergent abstractions are all mechanisms for this.

### Human judgment remains central

The system supports human judgment; it does not replace it. User approval, correction, and review are core parts of keeping the memory trustworthy.

### Simple mechanisms should do most of the work

The repo prefers plain files, summaries, logs, and clear rules over hidden automation or exotic infrastructure. The MCP tool surface adds programmatic convenience, but the underlying data remains human-readable markdown and YAML. The idea is to make the system robust enough that it can survive tool churn, model churn, and future redesigns.

## What this means in practice

If you use this system as intended, you should expect:

- a guided first session — either through a browser-based setup wizard or a collaborative onboarding conversation,
- much lighter returning sessions once summaries and routing are in place,
- explicit approval for high-impact system changes, with previews before commits,
- a browser dashboard for seeing what your memory contains without starting an AI session,
- governed writes through the MCP layer, with change categories enforced structurally,
- better long-term continuity across sessions and platforms,
- a memory that can be inspected, audited, and repaired instead of guessed at.

## When to read which document

- Read [QUICKSTART.md](QUICKSTART.md) if you want to set up or start using the system.
- Read this file if you want the core mental model and architectural rationale.
- Read [DESIGN.md](DESIGN.md) if you want deeper product philosophy, use cases, and future directions.
- Read [MCP.md](MCP.md) if you want the MCP tool surface explained for humans.
- Read [WORKTREE.md](WORKTREE.md) if you want to understand deployment modes (standalone, worktree, embedded).
- Read [INTEGRATIONS.md](INTEGRATIONS.md) if you want third-party tool integrations.
- Read [HELP.md](HELP.md) if you need troubleshooting guidance.
- Read [FIATLUX.md](../../FIATLUX.md) if you want the foundational philosophical and theological grounding for the system's deepest commitments.
- Read [GLOSSARY.md](GLOSSARY.md) if a term is unfamiliar.
- Read [README.md](../../README.md) if you need the full architecture and agent protocol reference.
