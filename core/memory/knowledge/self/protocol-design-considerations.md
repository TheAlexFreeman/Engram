---

title: Protocol Design Considerations for Engram
category: knowledge
tags: [engram, governance, protocol-design, self-knowledge, architecture]
source: agent-generated
trust: medium
origin_session: manual
created: 2026-03-21
last_verified: 2026-03-21
related:
  - engram-governance-model.md
  - operational-resilience-and-memetic-security-synthesis.md
---

# Protocol Design Considerations for Engram

What should inform the choice between formal protocol enforcement and open-ended
semantic interpretation when governing different aspects of this system? This
file captures the principles that emerged from the plans-to-projects overhaul
design review (2026-03-21) and from patterns observed across the existing
governance stack.

This is self-knowledge written during an active design phase. It should be
cross-checked against the system's actual behavior once the projects model is
implemented, and revised where experience contradicts the analysis.

---

## The core tension

Every protocol choice in this system sits on a spectrum between two failure modes:

1. **Over-formalization.** Rigid protocols that consume context budget, impose
   compliance overhead, and make the system feel bureaucratic rather than
   collaborative. The pathology: the agent spends more tokens on governance
   than on the user's actual work.

2. **Under-specification.** Loose conventions that drift across sessions, produce
   inconsistent behavior, and degrade tool-parseable surfaces into ad hoc prose.
   The pathology: the system can't build reliable automation because its own
   state is unpredictable.

The system already has a design principle for managing this tension — "measure
what you mandate" (DESIGN.md § Principles for dual-audience friendliness). But
that principle addresses *whether* to add governance. The question here is
*what kind* of governance: validator-enforced schema, tool-generated surfaces,
behavioral conventions described in prose, or open-ended semantic judgment?

---

## Factors that push toward formal protocols

**The surface is machine-read on the hot path.** If a file is loaded at session
start, parsed by MCP tools, or consumed by automations, its structure must be
predictable. The cost of schema enforcement is paid once (in tool code and
validator tests); the cost of parsing ambiguous markdown is paid every read.
This is why the projects navigator is a tool-generated table with
validator-enforced schema, and why per-project SUMMARY.md routing fields live
in YAML frontmatter rather than markdown body.

*System examples: `projects/SUMMARY.md` navigator table, per-project SUMMARY.md
frontmatter routing fields, `questions.md` machine IDs and `next_question_id`,
`projects/OUT/SUMMARY.md` recent-additions table, ACCESS.jsonl format.*

**The consequence of inconsistency is silent corruption.** If a question ID is
duplicated, a navigator row is stale, or an outbox entry has the wrong promotion
status, the error doesn't produce a visible failure — it produces subtly wrong
routing, stale context, or lost artifacts. Formal validation catches these before
they compound. Semantic interpretation cannot, because the interpreter (the
agent) has no ground truth to check against.

*System examples: question ID uniqueness in `questions.md`, navigator row count
matching actual project count, frontmatter field presence and type validation.*

**Multiple agents or automations must agree on the contract.** When different
sessions (or different agents in a multi-agent future) write to the same surface,
the protocol must be formal enough that independently instantiated agents produce
interoperable output. An agent that writes a project SUMMARY.md with the routing
fields in a different order, or with `cognitive_mode` spelled differently, breaks
the navigator generator for the next agent that runs it. Shared write surfaces
need schema-level agreement, not just convention.

*System examples: all MCP tool write targets — project SUMMARY.md frontmatter,
questions.md format, outbox SUMMARY.md format, ACCESS.jsonl entries.*

**The operation is high-frequency and benefits from elimination of judgment.**
If the agent performs an operation many times per session (logging access,
updating question counts, regenerating the navigator), the protocol should be
mechanical. Every invocation that requires the agent to exercise judgment about
format is a context cost and a consistency risk. The ideal: the MCP tool
enforces the protocol, and the agent's role is to decide *whether* to invoke the
tool, not *how* the tool's output is formatted.

*System examples: `memory_regenerate_navigator` (format is fully determined by
tool code), `memory_add_question` (ID allocation is automatic),
`memory_publish_to_outbox` (both summary sections updated atomically).*

---

## Factors that push toward semantic interpretation

**The surface is human-read or agent-read for comprehension, not routing.**
If a file's purpose is to convey understanding — design rationale, research
findings, reflection notes — then formal structure adds overhead without
improving the reader's experience. The markdown body of a project SUMMARY.md
exists for this reason: it carries narrative context that frontmatter cannot
express.

*System examples: project SUMMARY.md markdown body (description, cognitive mode
explanation, notes), `IN/` research files, knowledge base articles, session
reflections, DESIGN.md and other human-facing docs.*

**The judgment involved is irreducibly contextual.** Some decisions depend on
the specific content, the user's goals, or the state of the partnership —
they can't be reduced to a schema check. The question "should the cognitive mode
shift from exploration to evaluation?" requires understanding what was learned
this session, not checking a field against an enum. The orient–evaluate pattern
is a behavioral convention, not a validator rule, precisely because its value
comes from the agent exercising judgment about *when* and *how much* to apply it.

*System examples: cognitive mode transitions, orient–evaluate bracket depth,
Frame/Flag/Check activation threshold, question review ("is this still
relevant?"), cross-project knowledge relevance detection.*

**The protocol's value comes from adaptation, not consistency.** Some protocols
should behave differently as the system matures, as the user-agent relationship
develops, or as the task complexity varies. The Frame beat in the session-project
protocol is explicit in early sessions and telegraphic in mature partnerships.
The orient–evaluate bracket at single-task scale is thorough for novel domains
and minimal for routine knowledge files. Formal enforcement would freeze these
at one maturity level.

*System examples: Frame/Flag/Check maturity adaptation, orient–evaluate
bracket depth, trajectory review frequency, system-value assessment scope.*

**The cost of getting it slightly wrong is low and self-correcting.** If the
agent writes a slightly informal reflection note, or describes a cognitive mode
transition in a non-standard way, the system doesn't break — the next session
can correct it. Formal enforcement is only worth its complexity cost when errors
compound silently. For surfaces where the agent is the primary reader and can
tolerate variation, semantic interpretation is cheaper and more natural.

*System examples: session reflection notes, scratchpad entries, IN/ research
notes, project description prose.*

---

## The spectrum in practice

Mapping this system's surfaces from most-formal to most-semantic:

| Surface | Governance mode | Why |
|---|---|---|
| Frontmatter fields (all files) | Validator-enforced schema | Parsed by tools; silent corruption risk |
| Navigator table (`projects/SUMMARY.md`) | Tool-generated, validator-enforced | Highest-frequency read; multi-agent write surface |
| Outbox recent table (`projects/OUT/SUMMARY.md`) | Tool-generated | Automation scan surface; must be predictable |
| Question IDs and format (`questions.md`) | Validator-enforced format | Tool-addressable; duplication is silent corruption |
| Question `next_question_id` | Frontmatter field | Prevents ID allocation races |
| ACCESS.jsonl format | Schema-enforced | Aggregation pipeline depends on it |
| Outbox by-project index | Tool-generated | Human browsable but also tool-updated |
| Per-project SUMMARY.md body | Conventional sections | Agent-read for comprehension; variation tolerable |
| Orient–evaluate brackets | Behavioral convention | Value is in judgment, not consistency |
| Frame/Flag/Check protocol | Behavioral convention with maturity adaptation | Must evolve with the partnership |
| Cognitive mode transitions | Agent semantic judgment | Irreducibly contextual |
| `IN/` research content | Open-ended | Project-scoped working material; formal structure adds nothing |
| Session reflections | Open-ended | Ephemeral comprehension surface |

---

## Design heuristics for new protocols

When adding a new protocol or governed surface to this system, these questions
help locate it on the spectrum:

1. **Who reads this, and how often?** If it's tools or automations on the hot
   path → formal. If it's an agent reading for comprehension → conventional.
   If it's a human browsing → semantic.

2. **What happens if two sessions disagree about the format?** If disagreement
   causes silent data corruption or broken tooling → formal schema. If
   disagreement causes a slightly worse reading experience → convention is fine.

3. **Does the protocol's value come from consistency or from judgment?** If
   consistency (navigator table, question IDs) → formal. If judgment (when to
   run a trajectory review, how deep an orient bracket should be) → behavioral
   convention.

4. **Can an MCP tool enforce this without the agent's involvement?** If yes
   (navigator generation, ID allocation, outbox publishing) → make it a tool
   and formalize the output. If no (cognitive mode assessment, question
   relevance judgment) → it's inherently semantic.

5. **Will this protocol need to evolve with system maturity?** If yes → describe
   it as a convention with explicit maturity adaptation notes, not as a
   validator rule. Validator rules are expensive to change and tend to
   accumulate. Conventions can be tuned by updating a prose description.

6. **Does this earn its context budget?** (The "measure what you mandate"
   check.) Every formal protocol has a maintenance cost in validator complexity,
   tool code, and context tokens spent on compliance. The protocol must feed a
   feedback loop that measurably improves the system. If the answer is "it
   might prevent a problem someday," start with a convention and formalize
   later when evidence justifies the cost.

---

## Connection to the projects overhaul

The plans-to-projects overhaul (2026-03-21) made several protocol decisions that
instantiate these principles:

- **Routing fields in frontmatter** (formal) because the navigator generator and
  `memory_load_project` depend on them — machine-read, hot-path, multi-agent.
- **Tool-generated navigator** (formal) because it's the most frequently loaded
  orientation document and must be predictable for automations.
- **Hybrid outbox index** (formal for the recent table, conventional for the
  by-project index) because automations scan the recent table but humans browse
  the structured index.
- **Light questions.md frontmatter** (formal for `next_question_id` only)
  because ID allocation is a race-condition surface, but the question content
  itself is semantic.
- **Fixed question review thresholds** (formal: 3+ sessions, 10+ questions)
  rather than maturity-guided, because the system is in Exploration stage and
  doesn't yet have enough data to tune adaptive thresholds. Formalize now,
  revisit later — a deliberate application of heuristic 5.
- **Orient–evaluate brackets** (behavioral convention) because their value comes
  from the agent's judgment about when and how deeply to apply them.
- **Frame/Flag/Check protocol** (behavioral convention with maturity adaptation)
  because it must evolve with the partnership and its activation threshold is
  irreducibly contextual.

---

## What this file does not cover

- The specific validator rules and their implementation (see
  `HUMANS/tooling/tests/test_validate_memory_repo.py`).
- The instruction containment policy and folder behavioral contracts (see
  `core/governance/curation-policy.md` § "Instruction containment").
- The memetic security surface and governance layers (see
  `self/engram-governance-model.md`).
- The cognitive complementarity analysis that informs the human/agent division
  of labor in protocol design (see
  `knowledge/cognitive-science/human-llm-cognitive-complementarity.md`).

These are complementary perspectives on the same system. This file addresses the
meta-question of *when to formalize* — not *what the formalizations are* or
*why the human-agent collaboration is structured as it is*.
