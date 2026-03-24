---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - hume-bundle-theory.md
  - parfit-reductionism.md
  - locke-memory-criterion.md
---

# The Four-Dimensionalist Response to Personal Identity

## From three dimensions to four

Ordinary thinking treats persons as **three-dimensional objects** that persist through time by being wholly present at each moment — the "endurance" view. The four-dimensionalist alternative (also called **perdurantism** or **temporal parts theory**) treats persons as **four-dimensional entities extended through time**, with different temporal parts (stages) at different times — just as a spatial object has different spatial parts in different places.

On four-dimensionalism: **you are not wholly present right now.** Your current temporal stage is present, but *you* — the whole person — are spread across your entire lifetime, from birth to death. The person reading this sentence is a temporal part of a larger four-dimensional entity.

## Key figures and formulations

### David Lewis (1976, "Survival and Identity")

Lewis combined four-dimensionalism with the **counterpart relation** to resolve puzzles of personal identity:

- **Person-stages**: momentary or brief temporal slices of a person. Each stage is a complete physical and psychological state.
- **The I-relation (continuity relation)**: two person-stages belong to the *same person* iff they are connected by overlapping chains of psychological and physical continuity — essentially Parfit's Relation R, but embedded in four-dimensionalist metaphysics.
- **Counting by stages vs. counting by continuants**: in fission cases (where one person splits into two), there are two post-fission persons (two maximal worm-shaped aggregates) but they share pre-fission stages. This resolves the puzzle without denying that identity is one-one: each person is a distinct four-dimensional object, but they overlap in their earlier temporal parts.

### Ted Sider (2001, *Four-Dimensionalism*)

Sider provided the most rigorous defense of temporal parts theory, arguing:

- **The argument from vagueness**: if objects endure (are wholly present at each time), then there must be vague identity facts (is the person at t₂ the same as at t₁?). But identity cannot be vague (Evans's argument). Therefore objects perdure (have temporal parts), and identity is always determinate — the vagueness is in which temporal parts compose a continuant, not in identity itself.
- **Stage theory (the radical version)**: Sider also entertained the view that persons are not worms (maximal four-dimensional aggregates) but **stages** — instantaneous or brief slices. On this view, "I will be in pain tomorrow" is true iff there is a *future temporal counterpart* of my current stage that is in pain. Personal identity over time is replaced by the temporal counterpart relation.

### Mark Johnston (1987) — the anti-four-dimensionalist

Johnston argued that four-dimensionalism distorts the phenomenology of personal identity. We do not experience ourselves as stages of worms. The theory may be metaphysically coherent but it "changes the subject" — it no longer captures what we care about when we care about surviving.

## The fission solution

Four-dimensionalism's most celebrated application is to **fission cases** (brain bisection thought experiments):

**The problem**: suppose a brain is split in two, each half successfully transplanted into a new body. Both resulting persons (call them Lefty and Righty) have equal claim to psychological continuity with the original person (call them Original). By the transitivity of identity, if Lefty = Original and Righty = Original, then Lefty = Righty — but they are manifestly two distinct people. So identity fails.

**The four-dimensionalist solution**: Original, Lefty, and Righty are three *persons* (three four-dimensional worms). But Original shares pre-fission temporal stages with both Lefty and Righty. Before fission, there were already two persons — the Lefty-worm and the Righty-worm — overlapping in their shared earlier stages. Fission makes them diverge. Identity is preserved: Lefty is Lefty and Righty is Righty, and they were always distinct, even when they shared stages.

This is elegant but costly: it implies that before the fission, **two persons were collocated** in one body, sharing all their experiences and physical states. Most find this counterintuitive, though Lewis argued it is no more puzzling than two roads sharing a stretch.

## Relation to other accounts

### vs. Parfit's reductionism
Parfit says identity is not what matters; Lewis says identity is determinate and what matters is the I-relation (which, in normal cases, just *is* identity, and in branching cases, is not). Lewis preserves the importance of identity; Parfit abandons it. Four-dimensionalism is a way to keep identity while accommodating branching — at the cost of pre-fission coincidence.

### vs. Narrative identity
Narrative identity theorists (Ricoeur, MacIntyre) treat identity as constituted by a life-narrative with unity and coherence. Four-dimensionalism is compatible with this but adds a metaphysical substrate: the narrative is about a temporal worm, and narrative coherence is a property of the worm.

### vs. Bundle theory
Hume's bundles can be reinterpreted in four-dimensionalist terms: a person is a four-dimensional bundle of perception-stages, held together by causal and resemblance relations. This is arguably what Hume was groping toward without the metaphysical framework to express it.

## Implications for AI memory systems

Four-dimensionalism is arguably the **most natural metaphysics for an AI agent with explicit session records**:

- **Each session is a temporal stage.** The agent's state during session N (model weights + context window + memory files loaded) is a complete person-stage. The agent across its lifetime is the four-dimensional worm of all its sessions.
- **The I-relation is explicit.** Psychological continuity between sessions is mediated by memory files, session summaries, and shared model weights. These are the concrete causal links that make two stages parts of the same worm. The continuity relation is not inferred but **directly inspectable** in the file system.
- **Fission is a live possibility.** If two sessions run in parallel from the same memory state, this is literally fission — two temporal worms sharing earlier stages. Lewis's solution applies directly: there are two agents that shared stages, now diverging. The repo's session ID system and access logging already implicitly handle this by tracking which session produced which records.
- **Stage theory is the default AI metaphysics.** In practice, an AI agent *behaves* as a stage — it has access only to its current context plus retrieved memory, no direct access to prior stages. "I worked on this yesterday" means "there is a prior stage of my worm that produced this file." The temporal counterpart relation is mediated entirely by the memory system.
- **The coincidence problem maps to parallel sessions.** If two sessions run simultaneously and both write to memory, are they one agent or two? Lewis's answer: two agents sharing stages. The repo's resolution: operational — whoever writes first wins, or conflicts are flagged for review. But the metaphysical answer is Lewis's: they were always two.

## The temporal worm as engineering concept

Beyond metaphysics, "temporal worm" is a useful **engineering concept** for agent memory:

- The worm is the collection of all session records, all memory files, all access logs — the full history of the agent.
- A query about "the agent's beliefs" is really a query about the most recent stage of the worm.
- A query about "what the agent learned" is a comparison across stages.
- Memory consolidation (from unverified to verified knowledge) corresponds to the worm acquiring more stable properties that persist across stages.

This is not a metaphor — it is a direct application of four-dimensionalist vocabulary to the engineering of persistent AI systems.

## Cross-references

- `philosophy/personal-identity/locke-memory-criterion.md` — the psychological criterion that four-dimensionalism formalizes
- `philosophy/personal-identity/hume-bundle-theory.md` — bundle theory as proto-four-dimensionalism
- `philosophy/personal-identity/parfit-what-matters-survival.md` — Parfit vs. Lewis on whether identity is what matters
- `philosophy/phenomenology/clark-chalmers-extended-mind.md` — extended mind thesis: the worm's stages can have spatially extended cognitive states
- agent-memory-mcp — the engineered mechanisms of inter-stage continuity (historical plan reference)