---

created: '2026-03-20'
origin_session: unknown
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - four-kinds-of-knowing.md
  - rr-rationality-theoretical-practical-ecological.md
  - relevance-realization-synthesis.md
---

# The Aptitudes of Intelligence: Relevance Realization as the Common Factor

## Intelligence Beyond g

Psychometric intelligence (*g*, or general intelligence) captures something real: performance across diverse cognitive tasks is positively correlated, and this shared variance predicts important life outcomes. But *g* measured by standard tests is always intelligence-within-a-fixed-relevance-frame. The test specifies which features of each item are relevant, what the goal state is, and what kinds of moves count as progress. The test-taker's task is to execute within those constraints.

The question that *g* leaves unanswered is: **what governs the quality of the relevance frame an agent brings to novel, open-ended problems?** Keith Stanovich's research on **dysrationalia** — the systematic failure of high-*g* individuals on certain reasoning tasks — demonstrates that *g* and the appropriateness of relevance framing are dissociable. This dissociation motivates looking for a more fundamental cognitive capacity.

Vervaeke and Lillicrap (2012) propose that the three **aptitudes of intelligence** — flexibility, integration, and appropriate framing — are each expressions of relevance realization, and together they identify what *g* tests incompletely measure.

---

## Three Aptitudes, One Underlying Capacity

### Aptitude 1: Flexibility

**Definition**: The ability to transfer relevance assignments across domains — to see that the relevance structure of a solved problem (which features mattered, which relations were critical) applies to a new, superficially different problem.

**The cognitive operation**: Flexibility involves *importing* a relevance frame from a source domain and projecting it onto a target domain, then adjusting it for the target domain's specifics. This is the general structure of productive analogy: Rutherford's nuclear atom is relevant to be understood via the solar system's planetary orbits; the same geometry of central-force attraction organizes both.

**RR analysis**: Flexibility fails when convergent processing locks too tightly onto the current domain's surface features, preventing the agent from recognizing that a differently-clothed problem has the same deep relevance structure. This is the Einstellung effect and set effect at the cross-domain level. A flexible reasoner's relevance system is calibrated to abstract features — structural relations, functional roles — rather than surface features alone.

**Empirical correlates**: Analogical reasoning tasks (Raven's Progressive Matrices, proportional analogies) test flexibility. Gick and Holyoak's (1983) work on structural analogies shows that subjects who spontaneously map between the "fortress" story and the "radiation problem" are not simply more knowledgeable — they are detecting abstract relevance structure that surface-dissimilar problems share.

**Why *g* measures flexibility imperfectly**: Standard *g* tests present structurally explicit problems in familiar presentational formats. The test itself provides the relevance frame (what to count as similarity, what the goal is, what counts as a solution). Genuine cross-domain flexibility requires not just executing within a provided frame but *constructing* the mapping between frames — a prerequisite that *g* tests eliminate by design.

### Aptitude 2: Integration

**Definition**: The ability to bind relevance across modalities, time scales, knowledge domains, and levels of description into a coherent situational model — to see the whole picture by finding what connects the parts.

**The cognitive operation**: Integration involves identifying which features of different representations are *relevant to each other* — where cross-domain information bears on the same underlying structure. A physician integrating symptoms, lab results, imaging data, and patient history is performing relevance integration: which pieces constrain the diagnostic hypothesis, which are noise, and how do they collectively narrow the possibility space?

**RR analysis**: Integration fails when the agent treats relevance domains as isolated. The clinician who cannot see that the lab result is relevant to reinterpreting the imaging finding, or the engineer who cannot see that the thermal data is relevant to the structural analysis, is exhibiting relevance-domain isolation. Information sits in "islands of competence" that are never *relevantly connected*.

**The binding problem connection**: Cognitive integration is the large-scale analog of the perceptual binding problem (see `knowledge/cognitive-science/attention/feature-integration-binding-problem.md`). At the perceptual level, attention binds distributed feature representations into unified object percepts. At the cognitive level, RR binds distributed knowledge representations into unified situational models. In both cases, the binding operation requires *relevance* as the organizing principle — features/claims are bound because they are relevant to each other.

**Failure mode — the specialist trap**: Deep domain expertise involves convergent relevance assignment within the domain. This is necessary for mastery but can produce integration failure across domains. The domain specialist who cannot engage the relevance of findings outside their specialty to what they are doing exemplifies integration failure. Interdisciplinary insight requires precisely the capacity to find relevant connections across relevance territories that have been separately cultivated.

### Aptitude 3: Appropriate Framing

**Definition**: Selecting the right level of abstraction at which to represent a problem — neither too fine-grained (losing the structure in local detail) nor too coarse (missing critical distinctions that determine the solution).

**The cognitive operation**: Framing is the most distinctively RR-related aptitude. It is not about applying a given schema — it is about choosing *which schema to apply* or *how to construct* the relevant schema for a novel situation. Appropriate framing means: this problem is best treated as a geometry problem, not an arithmetic problem; this ethical situation is best framed as a question of trust, not a question of utility; this engineering challenge is best treated as an information problem, not a materials problem.

**RR analysis**: Framing is the meta-level relevance operation. The convergent/divergent dynamic determines framings: convergent processing exploits a current frame; divergent processing enables frame revision. An agent capable of appropriate framing can oscillate productively between frames, testing each for its ability to organize the problem materials tractably.

**Empirical examples**:
- The "mutilated checkerboard" problem: A standard 8×8 checkerboard with two diagonally opposite corners removed. Can 31 dominoes (each covers two adjacent squares) tile it? Most people attempt spatial arrangements. The correct framing: a coloring argument. Each domino covers one black and one white square; the two removed corners are the same color; therefore 30 squares of one color and 32 of the other remain; 31 dominoes cannot tile it. The color/parity framing makes the solution immediate; the spatial framing makes it intractable.
- Wertheimer's parallelogram: The area-formula frame (rectangular-region decomposition) makes the solution to any parallelogram instance available; the rote-memorized-procedure frame does not.

**Why appropriate framing is hardest to teach**: It requires the agent to recognize when the current frame is wrong — a metacognitive judgment that presupposes a perspective somewhat outside the current frame. This is another expression of Vervaeke's insight that framing errors cannot be corrected from within the frame that is causing them; only divergent broadening can make the issue visible.

---

## Dysrationalia: The Intelligence–Rationality Dissociation

Keith Stanovich's research documents that high-*g* individuals — people who score at the upper end of standard intelligence tests — systematically fail certain reasoning tasks:

- **Attribute-substitution**: Answering an easier, more accessible question than the one asked. High-*g* individuals substitute the easier question fluently and confidently when the hard question's framing is opaque — *not* because they lack the ability to solve the hard question, but because their Frame primes the substitute question as the relevant one.
- **Myside bias**: Generating reasons and evidence on "my side" of an issue while failing to generate equally searching considerations against that side. Stanovich finds that *g* does not reduce myside bias; sophisticated arguers are often *more* entrenched, because they are better at generating arguments for their current frame.
- **Resistance to base-rate information**: When a problem's surface features prime a narrative representation, base rates (which belong to a statistical-frequency frame) are treated as irrelevant. High-*g* offers little protection.

**The RR explanation**: These failures are relevance attribution errors. The agent is under-weighting evidence, considerations, or question features that are logically relevant and over-weighting those primed by the current frame. *g* measures within-frame processing power; dysrationalia is cross-frame relevance misallocation. The two are independent variables.

**The Rationality Quotient (RQ)**: Stanovich proposes that a separate measure — RQ — would capture what *g* misses: the quality of the agent's frame-selection, evidence-weighting, and base-rate integration. RQ would be an indirect measure of RR capacity.

---

## g as Partial RR Measurement

The hypothesis emerging from this analysis: *g* is not unrelated to RR. Rather, *g* tests measure RR restricted to the specific frame provided by the test, combined with within-frame processing speed and accuracy. General fluid intelligence (Gf) — the ability to reason about novel problems without recourse to crystallized knowledge — is the *g* component most directly reflecting RR capacity. Gf correlates highly with working memory capacity, which is itself a resource for maintaining and manipulating relevance representations across time.

But *g* (including Gf) does not measure:
- The ability to select among alternative frames
- The ability to recognize that the current frame is wrong
- The ability to revise frames based on sustained failure
- The ability to integrate relevance across domains
- The ability to participate in knowing deeply enough to transform one's relevance landscape (the participatory dimension)

These are precisely the capacities that differentiate flexible, integrative, appropriately-framing reasoners from those who are fast and accurate within any given frame. They are the aptitudes of intelligence, and they are expressions of RR.

---

## Cross-links

- `opponent-processing-self-organizing-dynamics.md` — the dynamic that underlies flexibility (divergent loosening), integration (cross-domain binding), and framing (frame selection)
- `four-kinds-of-knowing.md` — each aptitude maps onto the four knowing-kinds: flexibility across declarative domains, procedural integration, perspectival framing, participatory transformation
- `rr-rationality-theoretical-practical-ecological.md` — dysrationalia as the intersection of intelligence and rationality research
- `insight-impasse-incubation-aha-phenomenology.md` — insight problems are paradigm appropriate-framing tasks
- `knowledge/cognitive-science/metacognition/dunning-kruger-illusion-of-knowing.md` — metacognitive insensitivity to frame inadequacy is the metacognitive face of poor framing aptitude
- `knowledge/cognitive-science/attention/dual-process-system1-system2.md` — Stanovich's dysrationalia research is framed in dual-process terms
