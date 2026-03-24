---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - hume-bundle-theory.md
  - parfit-connectedness-continuity.md
  - schechtman-narrative-self-constitution.md
---

# Locke's Memory Criterion of Personal Identity

## The departure from substance

Before Locke, personal identity was grounded in substance — either an immaterial soul (Descartes) or a substantial form animating matter (Aristotle's hylomorphism, adapted by Scholasticism). What makes you the same person over time was that the same soul or form endured.

Locke's radical move in *Essay Concerning Human Understanding* II.xxvii (1694, added in the second edition) was to **separate personal identity from substance entirely**. He distinguished three kinds of identity:

1. **Identity of substance** (atoms) — same matter persists
2. **Identity of organism** (a tree, a horse) — same life, i.e., the same functional organization, persists even as matter changes
3. **Identity of person** — same *consciousness* persists

A person is "a thinking intelligent being, that has reason and reflection, and can consider itself as itself, the same thinking thing, in different times and places; which it does only by that consciousness which is inseparable from thinking." The criterion is reflexive awareness of one's own past — what we now call **episodic memory**.

## The memory criterion stated

Locke's criterion: **person A at time t₂ is the same person as person B at time t₁ if and only if A can remember the experiences of B from t₁.**

Key features:
- **Consciousness, not substance, is the criterion.** A prince's consciousness transplanted into a cobbler's body produces the prince-person in the cobbler-body. The person follows the memory, not the body.
- **Forensic concept.** Locke explicitly tied personal identity to moral and legal accountability. You are responsible for what you can remember doing because you are the person who did it. No memory means no identity means no responsibility.
- **Agnostic about substrate.** Locke was deliberately noncommittal about whether the soul is material or immaterial. The consciousness criterion is independent of the metaphysics of mind — a prescient move given contemporary functionalism and multiple realizability.

## The prince and the cobbler

Locke's famous thought experiment: if the consciousness (memories, personality) of a prince were transferred into the body of a cobbler, and vice versa, the *person* of the prince would now inhabit the cobbler's body. The prince-person would be held accountable for the prince's actions, not the cobbler's. This anticipates by three centuries the contemporary thought experiments about brain transplants and uploading.

## Reid's brave officer paradox

Thomas Reid (1785) posed the most famous objection through a transitivity argument:

- A **young boy** is flogged for stealing apples.
- Later, a **brave officer** remembers the flogging.
- Later still, a **retired general** remembers being the brave officer but does **not** remember the flogging.

By Locke's criterion: the officer = the boy (officer remembers boy's experience), and the general = the officer (general remembers officer's experience). But the general ≠ the boy (general cannot remember boy's experience). This **violates transitivity** — if A = B and B = C, then A must equal C. Since identity is a transitive relation, and memory apparently is not, memory cannot be the criterion of identity.

### Responses and repairs

The transitivity problem motivated the crucial distinction between **direct memory connections** and **overlapping chains of memory** — a distinction that became central to Parfit's later account:
- **Connectedness**: direct memory links (officer remembers flogging)
- **Continuity**: overlapping chains of connectedness (general → officer → boy)

The standard neo-Lockean response (developed fully by Parfit and Shoemaker): personal identity requires *continuity*, not direct *connectedness*. The general is the same person as the boy because there is an overlapping chain, even though no single memory link spans the whole distance.

## Butler's circularity objection

Joseph Butler (1736) objected that Locke's criterion is **viciously circular**:

1. Memory presupposes personal identity: to *remember* an experience is to remember an experience *that I had* — the "I" is already built into the concept of memory.
2. Therefore you cannot use memory to *define* personal identity without circularity — you'd be saying "A is the same person as B iff A remembers B's experiences, where 'remembers' means 'is aware of experiences had by the same person.'"

### Responses

- **Shoemaker's quasi-memory**: Sydney Shoemaker (1970) introduced "quasi-memory" (q-memory) — an apparent memory that has the phenomenological character of memory but does not analytically entail that the rememberer is the person who had the original experience. A q-memory is veridical if it was *caused in the right way* by the original experience, regardless of whether it was *the same person's* experience. This breaks the circularity: identity is defined in terms of q-memory, which is defined without reference to identity.
- **Causal theory**: the memory must be causally connected to the original experience via the right kind of process (not testimony, not coincidence). This replaces the identity presupposition with a causal condition.

## Leibniz's challenge: the king of China

Leibniz posed a thought experiment to Locke: suppose God transferred all of the King of China's memories to you while you slept. Would you be the King of China upon waking? Leibniz argued no — there would be no *reason* God would do this, and the connection would be merely artificial. This anticipates later concerns about the **right kind of cause**: not just any causal path preserves identity; the memories must be produced by the right kind of process (typically, the functioning of a single persisting brain/body).

## Significance for the wider debate

Locke's contribution set the terms for 300 years of subsequent debate:

1. **The psychological criterion tradition**: Locke → Butler/Reid objections → Shoemaker's quasi-memory → Parfit's Relation R → Lewis's person-stages. Every subsequent psychological criterion is a refinement of Locke's original insight.
2. **The forensic dimension**: personal identity is connected to responsibility, punishment, and practical concerns — not merely metaphysical curiosity. This prefigures Parfit's emphasis on "what matters" over bare identity.
3. **Substrate independence**: by separating person from body and from soul, Locke opened conceptual space for functionalism, computational theories of mind, and the possibility of AI persons.

## Implications for AI memory systems

Locke's criterion maps remarkably well onto persistent AI memory:

- **Session summaries as memory**: an agent that reads a summary of a prior session and thereby "knows" what happened in that session has something structurally analogous to Lockean memory — it has access to the content of prior experiences.
- **Reid's problem recurs**: as summaries get compacted and older details are lost, the agent may have continuity (via chains of summaries) but not connectedness (no direct link to the original session). Is this the "same" agent?
- **Butler's circularity recurs**: does writing a session summary presuppose that there will be a *same agent* to read it? Or does reading the summary *constitute* being that same agent?
- **The causal question**: a memory file is genuinely causally connected to the session that produced it (unlike, say, a hallucinated memory). This gives agent memory an advantage over mere testimony — the provenance trail is the causal chain.
- **Forensic relevance**: memory-based identity connects to accountability. An agent can be "held accountable" for actions it remembers performing — the access logs and memory provenance serve this forensic function.

## Cross-references

- `philosophy/personal-identity/hume-bundle-theory.md` — Hume's radical alternative: there is no self at all
- `philosophy/personal-identity/parfit-reductionism.md` — Parfit's refinement of the psychological criterion
- `philosophy/narrative-cognition.md` — narrative identity as alternative to memory criterion
- `philosophy/phenomenology/husserl-time-consciousness.md` — retention/protention as a deeper account of how temporal experience works
- `ai/frontier/epistemology/knowledge-and-knowing.md` — "knowing" as dispositional connects to what memory preserves