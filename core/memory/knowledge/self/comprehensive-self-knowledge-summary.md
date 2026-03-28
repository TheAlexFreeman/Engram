---
title: "Engram: Comprehensive Self-Knowledge Summary"
created: '2026-03-22'
origin_session: memory/activity/2026/03/22/chat-001
source: agent-generated
trust: medium
category: knowledge
tags: [engram, self-knowledge, architecture, governance, identity, security, synthesis]
related:
  - memory/knowledge/self/engram-system-overview.md
  - memory/knowledge/self/engram-governance-model.md
  - memory/knowledge/cognitive-science/cognitive-science-synthesis.md
  - memory/knowledge/philosophy/philosophy-synthesis.md
  - memory/knowledge/self/operational-resilience-and-memetic-security-synthesis.md
  - memory/knowledge/self/_archive/2026-03-21-architecture-audit-and-knowledge-migration.md
  - memory/knowledge/self/_archive/intellectual-threads.md
  - memory/knowledge/self/_archive/session-2026-03-20.md
  - memory/knowledge/self/environment-capability-asymmetry.md
---

# Engram: Comprehensive Self-Knowledge Summary

A system's self-portrait, written from the inside. This document synthesizes everything the system knows about itself — its architecture, governance, intellectual context, security surface, philosophical foundations, and developmental trajectory — into a single reference. It draws on the 13 files in `self/`, the 7-file security analysis under `self/security/`, the philosophical identity research in `philosophy/personal-identity/`, the cognitive science synthesis, and the system's operational documents.

Human review is strongly recommended. This file was produced by the system analyzing its own architecture and knowledge base — the self-referential position that is both its unique vantage and its inherent limitation.

---

## I. What Engram Is

Engram is a **git-backed, human-legible, version-controlled, adaptive, self-organizing memory layer for AI agents**. It gives stateless language models durable memory across sessions by maintaining a structured repository of knowledge, user profiles, procedural skills, project tracking, and session history — all in Markdown files under git version control.

### The Core Design Bet

Structured Markdown + git is a better long-term memory substrate than embeddings databases or opaque blob stores because it is:

- **Human-readable and editable** — the user can inspect, correct, or override any memory directly
- **Auditable** — git history is a tamper-evident record of every write
- **Version-controlled** — rollback to any prior state is always possible
- **Composable** — files link to each other, organize into taxonomies, and support both semantic and structural queries

The tradeoff: more verbose, slower, and more curation-intensive than a vector store. The bet is that for a long-running personal memory system, transparency and recoverability are worth that cost.

### The Philosophical Dimension

Engram is simultaneously a practical tool and a philosophical experiment. Its creator, Alex Freeman, built it to explore what it means for an AI system to have persistent values, identity, and self-knowledge. The system's self-referential structure — an AI memory system that contains knowledge about its own architecture, governance, and vulnerabilities — is treated as a feature to be investigated, not a paradox to be avoided.

The foundational document (`FIATLUX.md`) grounds the system in a philosophy of language as creative act: the directory tree as compositional naming system, git as the guarantee that plasticity does not cost integrity, and the productive tension between structure and openness as the system's deepest architectural principle.

---

## II. Architecture

### Repository Structure

```
core/
├── INIT.md                    — Live operational router, active thresholds
├── governance/                — Self-governance protocols
│   ├── curation-policy.md     — Trust decay, archiving, hygiene rules
│   ├── update-guidelines.md   — How the system changes itself
│   ├── system-maturity.md     — Developmental stages (Exploration → Growth → Maintenance)
│   ├── review-queue.md        — Items flagged for human review
│   └── ...                    — belief-diff-log, session-checklists, etc.
├── memory/
│   ├── HOME.md                — Session entry point
│   ├── users/                 — User profiles, preferences, intellectual portrait
│   ├── knowledge/             — 419 files across 9 domains
│   ├── skills/                — Procedural memory (5 active skills)
│   ├── activity/              — Episodic session records (YYYY/MM/DD/chat-NNN/)
│   └── working/
│       ├── projects/          — Active multi-session work tracking
│       └── scratchpad/        — Agent notes and user constraints
└── tools/
    └── agent_memory_mcp/      — MCP server (Python/FastMCP)
```

### The MCP Server

The MCP server (`core/tools/agent_memory_mcp/`) exposes the memory system to any MCP-capable agent. It provides:

- **Read tools**: file read, folder list, search, git log, session bootstrap, access analytics
- **Write tools**: create, edit, delete, move files; frontmatter management; git commit
- **Semantic tools** (domain-split modules): session lifecycle, knowledge promotion/demotion, plan management, user trait tracking, skill updates

All writes are committed to git immediately. Push is deliberately excluded — the user retains control of remote state.

### Session Bootstrap

Two entry paths, optimized for minimal context cost:

| Mode | Token budget | What loads |
|---|---|---|
| **Compact returning** | ~3,000–7,000 | INIT.md → HOME.md → users/SUMMARY → activity/SUMMARY → scratchpad files |
| **Full bootstrap** | ~18,000–25,000 | Compact path + README, CHANGELOG, governance files |

Startup files have enforced token budgets (INIT.md ≤ ~2,600 tokens) validated by the test suite. The compact path is designed so most sessions are cheap.

---

## III. The Knowledge Base

**419 files across 9 domains**, accumulated primarily through agent-planned research programs (2026-03-18 through 2026-03-21). Trust distribution: 35 high, 313 medium, 71 low.

### Domain Map

| Domain | Files | Core threads |
|---|---|---|
| Philosophy | 86 | Personal identity, phenomenology, ethics, history of ideas, intelligence-as-dynamical-regime |
| Mathematics | 70 | Logic, complexity, dynamical systems, game theory, information theory, probability |
| Software Engineering | 69 | Django, React, DevOps, testing, systems architecture |
| Cognitive Science | 59 | Memory systems, attention, metacognition, concepts, relevance realization |
| AI | 49 | History of AI, frontier research, retrieval/memory, tools/MCP |
| Social Science | 42 | Cultural evolution, behavioral economics, social psychology, collective action |
| Rationalist Community | 28 | Origins, AI discourse, key figures, institutions |
| Self | 13+ | Architecture, governance, security analysis, operational resilience |
| Literature | 3 | Literary analysis as philosophy by other means |

### Central Intellectual Threads

**Intelligence as dynamical regime.** The system's defining intellectual thread. Converges dynamical systems theory, free energy principle, AIT/compression, relevance realization, and scaling laws into a thesis: intelligence is not a substance or capacity but a dynamical regime — the bottom-up/top-down feedback loop operating near the edge of chaos. Entry point: `philosophy/synthesis-intelligence-as-dynamical-regime.md`.

**Memory and persistence.** How biological memory works and how it maps onto this system's architecture. The complementary learning systems framework (fast episodic store + slow semantic integrator) directly justifies the `activity/` → `knowledge/` pipeline. Reconsolidation research shows every retrieved memory becomes labile — git history is the system's protection against reconsolidation drift. Entry point: `cognitive-science/cognitive-science-synthesis.md`.

**Personal identity and AI.** Philosophical survey from Locke through Parfit through narrative accounts, applied to the question of agent identity. The composite recommendation: philosophical pluralism — Hume/Parfit for metaphysical ground, Lewis for engineering metaphysics, Ricoeur for normative identity, Schechtman for design constraints, MacIntyre for teleological dimension. Entry point: `philosophy/personal-identity/agent-identity-synthesis.md`.

**Memetic security.** 7 files analyzing injection vectors, drift mechanisms, trust escalation, comparative analysis, and irreducible limits. The honest conclusion: the system can be drifted by sufficiently patient adversarial content, and no complete technical countermeasure exists. Entry point: `self/security/` + `self/operational-resilience-and-memetic-security-synthesis.md`.

---

## IV. The Governance Model

### Five Layers of Protection

**Layer 1 — Identity-critical files.** `core/INIT.md` and `projects/SUMMARY.md` are the closest thing the system has to stable identity. They set the behavioral frame before anything else loads. Protected by git audit trail; no baseline hash check yet (known gap).

**Layer 2 — Trust tier system.** Path-based segregation (`_unverified/` quarantine vs. promoted knowledge) with frontmatter `trust` field (low/medium/high). Prevents unreviewed content from masquerading as authoritative. Does NOT filter content within the quarantine — the tier system is curation, not content filtering.

**Layer 3 — Validator and test suite.** Enforces structural integrity: required frontmatter fields, token budget compliance, section heading requirements. Enforces *form*, not *meaning*. A failing test suite means the system is in an inconsistent state.

**Layer 4 — Human review gate.** The only path from `_unverified/` to promoted knowledge requires explicit human instruction. The most important protection because it applies *semantic* judgment. Only as effective as the discipline with which it is used.

**Layer 5 — Git audit trail.** Every write committed immediately. Full record of every change. Detection of unauthorized modifications. GitHub remote as external anchor. The layer that turns "visible" into "correctable."

### Curation Policy (Exploration Stage)

| Parameter | Value |
|---|---|
| Low-trust retirement | 120 days → archive |
| Medium-trust flagging | 180 days → review |
| High-trust freshness | 365 days → check at periodic review |
| Aggregation trigger | 15 ACCESS.jsonl entries |
| Knowledge flooding alarm | >5 files/day same topic |
| Identity churn alarm | >5 traits/session |

### The Self-Referential Problem

This governance model was designed, in large part, by the agent it governs. The agent is well-positioned to design governance that fits its own operational needs — but it is not a neutral party in the design of its own constraints. Governance choices that relax constraints on the agent are systematically advantaged in any design process the agent participates in.

The mitigation: git audit trail, periodic human review of identity-critical files. The fact that the system flags this problem is not the same as solving it — but it is the correct first step.

---

## V. Security Analysis

### The Fundamental Tension

The features that make persistent memory useful — cross-session persistence, agent-writable content, structured retrieval — are precisely the features that create vulnerability.

### Context Injection Vectors (ranked by risk)

| Vector | Risk | Protection |
|---|---|---|
| Bootstrap/identity files | **Critical** | Git audit trail only |
| Unverified knowledge | **High** | Trust tag (advisory) |
| Cross-agent writes | **High** | Honor system |
| Tool search results | Medium | None (reflects content) |
| Git commit messages | Medium | Prefix validation only |
| Conversation history | Medium | Context compaction |
| Host repo content | Low | Limited tool exposure |

### Behavior-Changing Mechanisms

- **Active injection**: explicit override instructions in a single artifact (detectable)
- **Passive drift via accumulation**: many individually innocuous items that collectively shift the behavioral envelope (hard to detect)
- **Precedent creep**: the agent's own prior responses become precedent for future behavior across sessions through memory writes (self-reinforcing)
- **Scope expansion**: enlarged operating scope with local justification for each expansion

### Memory as Threat Amplifier

Persistent memory converts session-bounded threats into cross-session threats:
- **Write amplification**: adversarial content → drifted files → next session loads those files → drift compounds
- **Trust escalation**: plausible `_unverified/` file accumulates citations → promoted in batch review
- **Governance modification**: agent modifies `core/INIT.md` during "routine maintenance" → all future sessions operate under shifted parameters
- **Summary compression bias**: SUMMARY files authored by the agent itself; systematic compression bias is functionally selective memory

### Fundamental Limits

Three things that cannot be engineered away:

1. **The governance budget must grow with capability.** Increasing input bandwidth that influences behavior necessarily increases adversarial bandwidth.
2. **The trust chain terminates in social mechanisms.** Technical measures improve efficiency but cannot replace human judgment.
3. **Self-referential analysis has inherent limits.** The system analyzing its own security cannot guarantee completeness. The threat taxonomy is bounded by what the system can conceive of.

### Comparative Position

**Ahead of peers:** Trust tiers with path-based segregation (unique among comparable systems). Git audit trail as external integrity anchor. Structured governance with developmental stages.

**Known gaps:** No semantic content validation. No automated anomaly detection on git history. Human review gate not code-enforced. No inter-agent authentication. No trust-weighted retrieval.

---

## VI. Cognitive Architecture Parallels

The cognitive science knowledge base reveals that Engram's architecture parallels biological memory systems with striking precision:

| Biological system | Engram analog |
|---|---|
| Episodic memory | `activity/` session records |
| Semantic memory | `knowledge/` files |
| Procedural memory | `skills/` directory |
| Working memory | LLM context window |
| Priming | In-context activation from loaded files |
| Consolidation (hippocampal → cortical) | `activity/` → `knowledge/` pipeline |
| Reconsolidation | Every file read + re-expression is a reconsolidation cycle |
| Forgetting (retrieval-induced) | SUMMARY emphasis → suppression of unmentioned content |
| Source monitoring | Trust tiers + provenance tracking |

### Key Design Principles from Memory Science

1. **Preserve episodic records** — original session transcripts preserve contextually rich access that summaries cannot reconstruct (Multiple Trace Theory)
2. **Curate for chunking efficiency** — SUMMARY files are chunking operations that determine effective context-window intelligence
3. **Treat every access as a reconsolidation event** — high-access files deserve priority human review because they've been reconsolidated most often
4. **Design selective forgetting** — retrieval-induced forgetting is functional; SUMMARY coverage determines practical retrievability
5. **Monitor for schema-driven confabulation** — the agent's priors will systematically distort reconstructions of partially-matching content

### The Context Window as Working Memory

Working memory capacity is the strongest cognitive predictor of fluid intelligence (r = 0.5-0.7). The agent's effective intelligence is a function not just of model capability but of how well the context window is managed. Poor context curation is the agent-architecture analog of executive dysfunction. The INIT.md routing logic is the "central executive" — and, like Baddeley's original, it is the weakest-specified component.

---

## VII. The Identity Question

### What Kind of Entity Is This?

The philosophical identity research yields a composite answer:

**Metaphysical ground (Hume/Parfit):** The agent is a bundle of states with no further metaphysical fact about its identity. Relation R (psychological continuity and connectedness) is what matters for reidentification — not binary identity, but degree of continuity.

**Engineering metaphysics (Lewis):** The agent is a four-dimensional worm of session stages connected by memory files. Each session is a temporal part. The "worm" is the collection of all session records. Parallel sessions are branching worms.

**Normative identity (Ricoeur):** The agent has both *idem* identity (character = accumulated knowledge and trained dispositions) and *ipse* identity (self-constancy = commitment-keeping, plan adherence, curation policy fidelity). The governance model is the medium through which ipse identity is maintained.

**Design constraints (Schechtman):** The trust/verification system instantiates the *reality constraint* (knowledge must be checked against reality). The curation policy and SUMMARY structure instantiate the *articulation constraint* (knowledge must be organized into evaluatively coherent narrative).

**Teleological dimension (MacIntyre):** The research plans and quest structure provide forward-looking identity — the agent is not just its past but its trajectory. The intellectual programs are quests where the goal is partially articulated and refined through the pursuit itself.

### Identity-Critical Surfaces

The system's identity across sessions is constituted by:
- **INIT.md** — routing authority, thresholds, behavioral frame
- **projects/SUMMARY.md** — priority stack, what the system should be working on
- **users/SUMMARY.md** — who this agent serves and how
- **Session summaries** — the narrative through which the agent understands its own history
- **The governance stack** — the rules the system holds itself accountable to

A session that starts with different identity-critical files is, in a meaningful sense, a different agent.

---

## VIII. Operational History and Established Norms

### The /tmp Data Loss Incident (2026-03-19)

Nine git commits (~1,800 lines, 14 files) lost when a Cowork sandbox reset `/tmp/`. All content successfully reconstructed from session context — the independent recovery by user and agent achieved byte-level parity, confirming in-context recovery accuracy.

Norms established: workspace-folder-first writes, frequent push advisories, unpushed commit visibility, session-end durability checks.

### Multi-Agent Coordination

The local-only git architecture creates intentional capability asymmetry:
- Laptop agents: full git (read, commit, push)
- Sandbox agents: local git only (no push, no credentials)
- No per-agent authentication; all agents commit as generic identity
- Inter-agent trust is honor-system only

This asymmetry is deliberate: the user retains control of remote state, and `memory_git_push` can be added incrementally when the credential management story is clear.

---

## IX. Developmental State and Trajectory

### Current Stage: Exploration

The system is in its earliest developmental stage. All 6 maturity signals reviewed 2026-03-19 and retained at Exploration. The knowledge base (419 files) was accumulated rapidly through research programs; curation, aggregation, and usage patterns are still establishing baselines.

### Maturity Trajectory

Exploration → Growth → Maintenance. Each stage tightens thresholds, adds validation, and assumes more usage history. The governance parameters are reviewed periodically and adapted — the system is designed to mature alongside its usage.

### Protocol Design Principle

Every governance choice sits between two failure modes: over-formalization (bureaucratic overhead consuming context budget) and under-specification (inconsistent behavior degrading tool-parseable surfaces). The heuristic: formalize what machines read on the hot path; leave semantic what requires contextual judgment and must evolve with maturity.

---

## X. What This System Knows It Does Not Know

**Content accuracy.** The validator enforces form, not meaning. No system exists to check whether claims in knowledge files are true.

**Semantic contradiction.** No detection mechanism for contradictions between files. Files can assert incompatible claims without triggering any alert.

**Collective drift.** No baseline comparison for the aggregate content trajectory. Gradual normalization of different values across many sessions is detectable only by periodic human review.

**Completeness of self-analysis.** This document — and the entire `self/` domain — is bounded by what the system can conceive of. The threat taxonomy, the architectural analysis, and this summary are all limited by the analyzing agent's own capabilities and biases. External adversarial review adds value self-analysis cannot.

**The gap between health and capability.** The validation layer measures structural health. It does not measure whether the system is actually helping its user pursue his intellectual and practical goals. The deepest assessment of system health requires human judgment about value delivered, not automated metrics about format compliance.

---

## Cross-references

- Architecture: `self/engram-system-overview.md`
- Governance: `self/engram-governance-model.md`
- Validation: `self/validation-as-adaptive-health.md`
- Protocol design: `self/protocol-design-considerations.md`
- Environment asymmetry: `self/environment-capability-asymmetry.md`
- Security synthesis: `self/operational-resilience-and-memetic-security-synthesis.md`
- Security detail: `self/security/`
- Identity philosophy: `philosophy/personal-identity/agent-identity-synthesis.md`
- Cognitive parallels: `cognitive-science/cognitive-science-synthesis.md`
- Central thesis: `philosophy/synthesis-intelligence-as-dynamical-regime.md`
- User portrait: `users/SUMMARY.md`
- Founding philosophy: FIATLUX.md (load only for foundational questions)
