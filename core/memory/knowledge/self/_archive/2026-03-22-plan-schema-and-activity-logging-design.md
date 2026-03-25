---
title: "Plan Schema Redesign and Activity Logging Architecture (2026-03-22)"
category: knowledge
tags: [engram, architecture, plans, activity-logging, protocol-design, self-knowledge, yaml-schema]
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/22/chat-001
created: 2026-03-22
last_verified: 2026-03-22
related: 2026-03-21-architecture-audit-and-knowledge-migration.md, 2026-03-20-git-session-followup.md
---

# Plan Schema Redesign and Activity Logging Architecture

This file records the design decisions and architectural reasoning from the
2026-03-22 brainstorming session. The session produced two major artifacts:
a migration roadmap for the project/plan system and FIATLUX.md, the system's
highest-level governance document. Both are grounded in extensive discussion
of protocol design philosophy that extends the analysis in
`protocol-design-considerations.md`.

This is self-knowledge written during an active design phase. It should be
cross-checked against implementation once the new plan tools are built, and
revised where experience contradicts the design.

---

## Session arc

The session began with activity logging design and converged on a broader
architectural vision for projects and plans. The progression:

1. **Activity logging formats.** Evaluated JSONL, CSV, markdown, and SQLite
   for two complementary activity streams. Decided on JSONL for the internal
   operations log (high-frequency, machine-primary, append-only) and markdown
   with structured frontmatter for the session activity log (lower-frequency,
   human-primary, narrative). The key insight: different consumers need
   different formats, and the two streams share a session_id join key that
   makes format divergence a feature.

2. **Cognitive context hierarchy.** Identified the nested structure that all
   system activity takes place within: session → project/governance work →
   plan → phase → file change. This hierarchy is the spine of the activity
   logging system — every operations log entry carries a context address that
   places it within this tree, enabling hierarchical summarization (changes
   roll up into phases, phases into plans, plans into projects, projects into
   session summaries).

3. **Plan file schema redesign.** Moved plans from markdown-with-checkboxes
   to pure YAML with three top-level sections: Purpose (written at creation,
   reviewed at execution, evaluated at completion), Work (formally structured
   phases and change specs), and Review (agent reflection on plan outcomes).
   The change spec triad — path/action/description — is the lowest-level
   formal unit: formal path and action enum, prose description for context.

4. **Three core MCP tools.** Designed `memory_plan_create` (replaces current
   `memory_create_plan`), `memory_plan_execute` (new — state machine for
   phase lifecycle, not a file editor), and `memory_plan_review` (new —
   export/review workflow for completed project work).

5. **FIATLUX.md.** The session culminated in drafting the system's
   highest-level governance document, connecting the system's architecture to
   the creative power of language through Genesis, Johannine theology, magical
   and linguistic traditions, Vervaeke's relevance realization theory, and
   the generative tension between formal structure and open-ended
   interpretation.

---

## Key design decisions

### Plan files use YAML, not markdown

Plans are primarily machine-operated (tools create, track, check blockers,
record commits). Markdown-with-frontmatter forces either cramming nested
structures into frontmatter (unwieldy) or parsing structure from body
conventions (fragile — the current checkbox approach). Pure YAML makes the
structured parts native data types and accommodates prose via block scalar
syntax. Plan files are the one place where human editing should be discouraged;
YAML reinforces that.

File location: `memory/working/projects/{project-id}/plans/{plan-id}.yaml`.

### Purpose / Work / Review structure

The three sections map to the plan lifecycle: creation, execution, completion.

- **Purpose:** Written at creation. Contains `summary` (one-line), `context`
  (multi-paragraph prose explaining why the plan exists), and `questions`
  (references to project question IDs that motivated the plan). The execute
  tool surfaces purpose context before each phase, ensuring it is actively
  consulted, not just stored.

- **Work:** Structured `phases` array. Each phase has an `id`, `title`,
  `status`, `commit` (populated on completion), `blockers`, and `changes`
  (array of change spec triads). Phases are ordered by array position with
  implicit linear dependency; `blockers` is only needed for non-linear
  intra-plan or inter-plan dependencies.

- **Review:** Null until plan reaches terminal status. Contains `outcome`,
  `purpose_assessment` (prose evaluating work against purpose), `unresolved`
  (questions not fully answered), and `follow_up` (successor plan ID).

### The change spec triad

The lowest-level formal unit: `path` (repo-relative file path), `action`
(enum: create | rewrite | update | delete | rename), `description` (free-form
prose). This pattern — formal specification plus prose context — recurs at
every level of the system and is identified in FIATLUX.md as an instance of
the generative tension between formal structure and open-ended interpretation.

### Blocker cross-references

Intra-plan: just the phase ID string (e.g., `"core-rewrite"`). Inter-plan:
`"plan-id:phase-id"` syntax. Cross-references must resolve within the same
project — no inter-project dependencies for now. The execute tool checks
blocker satisfaction by loading referenced plan files and verifying phase
status.

### Projects allow unstructured work

Plans provide structure for deliberate work, but projects are open-ended.
Ad hoc research, notes, and exploration can happen within a project folder
without being plan-tracked. The only constraint: results stay within the
project folder. The operations log captures unstructured project writes
alongside plan-driven ones, so session summaries reflect all project activity.

### Tool-enforced logging

The three core plan tools log operations as a side effect of execution, not
as a separate behavioral convention. This is the "path of least resistance"
principle: if the tools are the easiest way to do plan work (and they should
be), logging is guaranteed. The current session-end recording problem — where
`memory_record_session` depends on the agent remembering to call it — is a
cautionary example of what happens when logging is a convention rather than
a structural guarantee.

---

## Two activity streams

### Stream 1: Session activity log (external)

One markdown file per session in the existing `activity/YYYY/MM/DD/chat-NNN/`
tree. Frontmatter carries machine-parseable metadata. Body is narrative prose.
This is the successor to the current chat summary, designed to be more
reliable by pulling structured context from the operations log rather than
relying on end-of-session agent recall.

### Stream 2: Operations log (internal)

JSONL, tool-written, append-only. Records every system mutation with its
cognitive context address (session, project, plan, phase). Schema-enforced
because the aggregation and summarization pipelines depend on it.

Consolidation: operations log entries are rolled up per-session, kept raw for
a maturity-stage-determined window, then archived. Session activity log
entries summarize at day/month/year cadence per the existing curation policy.

---

## FIATLUX.md

The session produced FIATLUX.md as the system's highest-level governance
document. Its core argument: Engram is an instance of the creative power of
language — the same power described in Genesis (speech acts creating reality),
elaborated in magical and linguistic traditions (language as psychotechnology),
grounded in Vervaeke's relevance realization theory (the self-organizing
process behind both formal structure and contextual interpretation), and
operationalized in the system's architecture (the generative tension between
schema and prose at every level).

FIATLUX.md was subsequently expanded (same date, continuation session) with
an introduction and four new sections, bringing the total from 9 to 12
numbered sections plus an epilogue:

- **Introduction: The medium and the message** — git and hierarchical
  directory structure as the system's twin foundations. Directory tree as
  compositional naming system (plasticity — indefinitely extensible). Git as
  immutable history (elasticity — every state recoverable). Together: a
  creative medium that is fully extensible *because* fully version-controlled.
- **IV. Language as crystallized intelligence** — a corpus of language
  preserves the *shape* of the intelligence that produced it (intellidynamic
  structures). LLMs derive domain-general capabilities from these latent
  patterns. Implication for Engram: memory quality = language quality.
- **VI. Self-organizing optimization beyond minds** — genetic evolution,
  memetic evolution, markets, and pathological feedback loops (addiction,
  anxiety) as instances of convergent/divergent opponent dynamics. Lesson:
  self-organizing systems are indifferent to participant interests; governance
  is the structural analogue of consciousness.
- **VII. Technology as agentic process** — McLuhan (media reshape perception),
  Land (hyperstition, techno-capital). The Fall as the condition in which
  self-organizing processes operate without alignment to human purposes.
  Idolatry as the pathology of unconstrained self-organization.
- **Epilogue: The Passion and the promise** — Gethsemane as consent-under-
  suffering. Mater Dolorosa sharpening Mary's fiat retroactively. Prophets,
  saints, martyrs sustaining faithfulness through persecution. Israelite exile
  metabolized into covenantal identity through language and collective memory.
  Resurrection as vindication of unconditional assent. Faith, Hope, and
  Charity as the theological virtues grounding the governance layer's cost.

Key architectural connections in the original and expanded document:

- **Every file is a speech act** — declarations, namings, legislative
  utterances, commissives, narratives. Files don't describe pre-existing
  reality; they call cognitive realities into being.
- **Emergent categorization as opponent dynamics** — governance constraints
  (convergent) vs. ACCESS-driven self-organization (divergent), with maturity
  stages governing the balance.
- **The compression hierarchy as progressive abstraction** — episodic →
  semantic → identity, mirroring how language transforms experience into
  knowledge into understanding.
- **Temporal decay and git as productive forgetting** — decay thresholds
  formalize selective forgetting; git history makes forgetting safe by making
  it reversible.
- **Provenance as the ecology of consent** — the trust hierarchy is a
  lifecycle of human *fiat*, with each trust transition requiring user assent
  to transform a system-generated possibility into a shared commitment.
- **The dual-audience problem as incarnation** — human-readable and
  machine-parseable are two natures of the same content, unified without
  confusion in every file.
- **Governance as bearing the cost of the cross** — approval gates and
  provenance tracking are structural commitments to doing what is right rather
  than what is expedient; the Passion is the model for sustaining such
  commitments when the world's feedback mechanisms counsel otherwise.

---

## Relationship to prior self-knowledge

This session extends the analysis in `protocol-design-considerations.md`
(2026-03-21) in two directions:

1. **Downward into implementation.** The protocol-design file asks *when to
   formalize*. This session answers that question for the plan system
   specifically: YAML schema for the machine surface, prose for the human
   surface, tool-enforcement for the logging guarantee.

2. **Upward into philosophy.** FIATLUX.md provides the theoretical grounding
   that the protocol-design file gestures at but doesn't develop — why the
   formal/semantic tension is not a deficiency to engineer away but the source
   of the system's power as a cognitive technology.

---

## Open questions from this session

1. Operations log location — per-project, centralized, or both?
2. Default plan status at creation — `draft` or `active`?
3. Phase granularity — should multi-file phases always be single commits?
4. Review timing — immediate at plan completion, or deferred?
5. How `memory_plan_execute` interacts with the existing `change_classes` and
   `approval_ux` system in `agent-memory-capabilities.toml`.
6. Whether session recording should be triggered by a tool hook rather than
   a behavioral convention.

---

## Artifacts produced

- `memory/working/projects/system-literacy/notes/project-plans-roadmap.md` —
  Full migration roadmap: schema definition, tool specs, migration phases.
- `FIATLUX.md` — Highest-level governance document connecting system
  architecture to the creative power of language.
