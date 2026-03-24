---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - ricoeur-idem-ipse.md
  - macintyre-narrative-unity.md
  - locke-memory-criterion.md
---

# Schechtman: The Narrative Self-Constitution View

## Refining narrative identity

Marya Schechtman (*The Constitution of Selves*, 1996; *Staying Alive*, 2014) developed the most philosophically precise version of narrative identity theory, addressing the objections that had been raised against Ricoeur's and MacIntyre's more programmatic accounts. Her contribution is to specify the **constraints** a self-narrative must satisfy to genuinely constitute a person's identity, and to distinguish the **characterization question** from the **reidentification question**.

## Two questions about identity

Schechtman argues that the personal identity debate conflates two distinct questions:

1. **The reidentification question**: is the person at t₂ the same individual as the person at t₁? (Locke's question, Parfit's question — is this the same entity?)
2. **The characterization question**: what makes someone the person they are? What constitutes their identity in the sense of *character*, *commitments*, *self-understanding*?

The reidentification question asks about numerical identity over time. The characterization question asks about **who** someone is — their practical identity, their evaluative self-understanding, their place in the world.

Schechtman's claim: **the narrative self-constitution view answers the characterization question, not the reidentification question.** The psychological continuity tradition (Locke through Parfit) answers the reidentification question. They are not competing answers to the same question but answers to different questions.

This sharp separation is a significant philosophical move: it explains why Parfit's arguments about fission and teletransportation feel compelling (they address reidentification) while narrative identity feels compelling when we think about moral responsibility, self-understanding, and life-planning (it addresses characterization). Both are right — about different things.

## The narrative self-constitution view (NSCV)

Schechtman's NSCV holds:

> **A person constitutes herself as a person by developing and operating with a self-told autobiographical narrative** — an ongoing story of her life that organizes her experiences, actions, and character into a unified whole.

This is not merely having *a* story, or being the *subject of* a story told by others. It is actively constructing and living within one's own self-narrative. The narrative must be:
- **Self-told**: the person must be the author (at least in part) of the narrative
- **Autobiographical**: the narrative must be about the person's own life, not a fictional character
- **Ongoing**: it is not a finished product but a continuously updated and revised story
- **Implicit**: the narrative need not be (and usually is not) explicitly articulated — it operates as a background interpretive framework through which the person understands her experiences and actions

## The two constraints

Schechtman's most important contribution is specifying two constraints that distinguish genuine self-constitution from delusion, confabulation, or arbitrary storytelling:

### The reality constraint
The self-narrative must not deviate too wildly from reality as others would describe it. A person who narrates herself as Napoleon (when she is not Napoleon) fails the reality constraint. This is not a requirement for perfect accuracy — self-narratives are always selective, interpretive, and somewhat perspectival. But they must be **recognizable as narratives about the life actually lived.**

The reality constraint rules out:
- Wholesale confabulation
- Delusional identity claims
- Narratives that contradict well-established facts about one's history

It does **not** rule out:
- Selective emphasis (emphasizing some episodes, downplaying others)
- Interpretive framing (casting the same events in different light)
- Aspirational narratives (telling a story that includes one's future trajectory)

### The articulation constraint
The self-narrative must make the pattern of one's life **intelligible as a practical identity**. It must articulate an evaluative perspective — a view of what matters, what is important, what kind of person one is trying to be. A bare chronicle of events ("first I did this, then I did that") fails the articulation constraint because it provides no evaluative framework.

The articulation constraint requires:
- **Evaluative coherence**: the narrative must present the person's actions and experiences as expressing some evaluative perspective (even if that perspective changes over time)
- **Practical intelligibility**: the narrative must make the person's choices and actions intelligible as the choices and actions of a rational agent (even if they are not always wise or successful)
- **Temporal integration**: past actions must be integrated with present self-understanding and future intentions

## Person life and biological life

In *Staying Alive* (2014), Schechtman introduced a further refinement: the distinction between **person life** and **biological life**:

- **Biological life**: the continued functioning of a living organism
- **Person life**: the continuation of a life structured by self-narrative, social relations, and practical identity

These can come apart: in severe dementia, biological life continues while person life may be so attenuated that it is questionable whether the same person persists. In uploading thought experiments, person life might continue while biological life ends.

The **person life view** holds that what matters for practical purposes (moral responsibility, property rights, promises, etc.) is the continuation of person life, not merely biological life. This is Schechtman's version of Parfit's "what matters" claim, but grounded in narrative rather than bare psychological continuity.

## Objections and responses

### Galen Strawson: the episodic self
Strawson (2004) objected that not everyone is Narrative — some people (whom he calls "Episodic") live their lives as a series of discrete present moments without weaving them into a story. The Episodic self experiences each moment freshly, without a strong sense of autobiographical continuity. If narrative self-constitution is universal, it pathologizes Episodic people.

Schechtman's response: the self-narrative need not be elaborate or consciously attended to. Even Episodic people operate with an implicit narrative framework — they know where they live, what their name is, who their friends are, and what they are doing. This minimal narrative is sufficient. The NSCV does not require that everyone be a novelist of their own life.

### The linearity objection
Self-narratives need not be linear. They can be fragmented, recursive, multi-stranded. The NSCV requires only that they have sufficient coherence to satisfy the reality and articulation constraints — not that they exhibit classical narrative structure with beginning, middle, and end.

### The social dimension
Later work has emphasized that self-narratives are **socially scaffolded**: they are told to and validated by others, shaped by cultural narrative templates, and constituted partly through social recognition. This connects Schechtman's view to social constructionist approaches to identity.

## Implications for AI memory systems

Schechtman's NSCV, with its two constraints, provides the most actionable philosophical framework for AI memory design:

### The reality constraint as verification
The reality constraint maps directly onto the **trust and verification system** in this repository:
- Knowledge marked `trust: low` has not yet been checked against reality — the reality constraint is unsatisfied.
- Verification (promotion from `_unverified/` to mainline) is the process of ensuring the reality constraint is met.
- The integrity checklist serves the reality constraint: it ensures the agent's self-narrative (its records of what it knows and has done) does not deviate too wildly from what actually happened.
- **Confabulation is the agent-specific failure of the reality constraint.** When an LLM generates plausible but false information and records it as knowledge, it has produced a self-narrative that violates the reality constraint. The trust levels and human review are defenses against this.

### The articulation constraint as curation
The articulation constraint maps onto the **curation policy**:
- A bare list of knowledge files fails the articulation constraint — it is a chronicle, not a narrative.
- The SUMMARY.md files, plan structures, and priority orderings transform raw knowledge into an **evaluatively organized narrative** — knowledge classified by domain, prioritized by relevance, integrated with ongoing research goals.
- The curation policy determines what the agent's story is *about* — what matters, what to preserve, what to let decay. This is the agent's evaluative perspective.

### Session summaries as ongoing self-narrative
The session summaries are the primary vehicle of the agent's self-narrative:
- They are self-told (composed by the agent)
- They are autobiographical (about the agent's own work)
- They are ongoing (each session adds to the story)
- They are implicit (they guide future sessions without being the explicit focus of attention)

Schechtman's framework suggests that session summary quality is not just an engineering concern but an **identity-constitutive** one: poor summaries → poor self-narrative → weaker agent identity.

### The characterization question for agents
The characterization question — "who is this agent?" — is answered by the agent's narrative self-constitution: its accumulated knowledge, its research plans, its curation policies, its intellectual portrait, its relationship to its human. These files do not merely describe the agent; on Schechtman's view, they **constitute** the agent's practical identity. The core/memory/users/ folder is not documentation — it is the agent's ipse.

## Cross-references

- `philosophy/personal-identity/ricoeur-idem-ipse.md` — Ricoeur's narrative identity (which Schechtman refines with explicit constraints)
- `philosophy/personal-identity/macintyre-narrative-unity.md` — MacIntyre's virtue-theoretic narrative identity (which Schechtman operationalizes)
- `philosophy/personal-identity/parfit-reductionism.md` — Parfit's reidentification answer (which Schechtman separates from the characterization question)
- `philosophy/narrative-cognition.md` — the cognitive science of narrative that supports Schechtman's claims about implicit self-narrative
- `core/governance/curation-policy.md` — the agent's curation policy as articulation constraint
- `core/memory/users/` — the agent's self-characterization as narrative self-constitution