---
created: '2026-03-20'
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: medium
related: boyd-richerson-dual-inheritance.md, dawkins-meme-concept.md, llms-cultural-evolution-mechanism.md, blackmore-meme-machine.md, fricker-epistemic-injustice.md, norms-punishment-cultural-group-selection.md, idea-fitness-vs-truth.md, henrich-collective-brain.md
---

# Hull: The Replicator/Interactor Framework

## Background

David Hull (1935–2010) was a philosopher of biology who developed the most rigorous general framework for evolutionary processes. His key contribution was distinguishing **replicators** from **interactors** and applying this framework to the evolution of science itself. Hull's work provides the conceptual precision that Dawkins's original meme concept lacked.

## The Replicator/Interactor Distinction

### Definitions

Hull (1980, 1988) proposed that any evolutionary process requires two kinds of entities:

- **Replicator**: an entity that passes on its structure largely intact in successive replications. The key property is *informational fidelity* across copies.
- **Interactor**: an entity that interacts as a cohesive whole with its environment in such a way that replication is differential. The key property is *causal engagement* with selective forces.

In biological evolution:
- **Gene** = replicator (passes on its structure through DNA replication)
- **Organism** = interactor (engages with the environment; differential survival and reproduction determines which genes are replicated)

The critical insight: **replicators and interactors are functional roles**, not fixed ontological categories. The same entity can be a replicator at one level and an interactor at another. A gene is a replicator in the context of DNA copying, but a gene complex can function as an interactor in the context of selection among gene complexes.

### Why Two Roles Matter

Dawkins had focused almost exclusively on the replicator. His "selfish gene" framework asked: which replicators increase in frequency? But this left the mechanism of selection underspecified. Hull's contribution was insisting that you need to track *both*:

1. **What gets copied?** (replicator question)
2. **What faces selection?** (interactor question)

These can be different entities at different levels. In biological evolution, the gene is copied but the organism faces selection. In cultural evolution, the meme is (purportedly) copied but the behavioral pattern or cognitive structure faces selection.

### Comparison with Dawkins

| Concept | Dawkins | Hull |
|---------|---------|------|
| Replicator | Gene, meme | Any entity with high-fidelity copying |
| Vehicle/Interactor | Organism (vehicle) | Any entity that cohesively engages selective forces |
| Emphasis | Replicator-centered | Both roles equally important |
| Framework scope | Biology + culture (by analogy) | General evolutionary theory (any domain) |

Hull explicitly rejected Dawkins's term "vehicle" as too passive — it implies the organism is merely a carrier for genes. "Interactor" emphasizes that the entity *actively engages* with its environment, and that this engagement is what drives differential replication.

## Application to Science

### Science as an Evolutionary Process (*Science as a Process*, 1988)

Hull's most sustained empirical application was to the evolution of scientific ideas. He studied the systematics community (taxonomists) as a test case, tracking the spread of competing classificatory methods (phenetics vs. cladistics) across research groups over decades.

#### The Mapping

| Biological evolution | Scientific evolution |
|---------------------|---------------------|
| Gene (replicator) | Concept, theory, method (replicator) |
| Organism (interactor) | Scientist, research group (interactor) |
| Population | Scientific community |
| Ecological niche | Problem domain |
| Fitness | Conceptual inclusiveness, empirical adequacy, adoption rate |

#### Key Finding: Credit and Cooperation

Hull discovered that the key dynamics driving idea-selection in science were **credit** and **cooperation**:

- Scientists are motivated by credit (recognition, citation, priority). This creates a competitive environment that selects for useful ideas — but also for ideas that advance careers.
- Scientists cooperate in research groups, creating interactors at the group level. A research group collectively faces selection; if its ideas fail, the group dissolves.
- Use of others' ideas without credit is heavily punished (plagiarism norms), which enforces a kind of intellectual honesty — you must acknowledge your sources, creating lineage tracking.
- Priority disputes (Dawkins/Williams vs. Hamilton, for instance) are not mere ego conflicts — they are selection events in which conceptual lineages compete for adoption.

### Credit as the Selection Mechanism

The credit economy in science functions like differential reproduction:
- Ideas that others cite and build on "reproduce" (memetic fitness = citation/adoption)
- Ideas that nobody cites "die" (archived, forgotten)
- Credit incentivizes both originality (novel mutations) and accuracy (fitness = empirical adequacy)
- But credit also incentivizes self-promotion, strategic citation, and empire-building (fitness ≠ truth)

This analysis anticipates the modern replication crisis: when the selection mechanism (credit/publication) rewards novelty and positive results over accuracy and replication, the evolutionary system selects for striking-but-fragile findings over robust-but-boring ones.

## Conceptual Precision: Beyond Memes

### What Hull Adds

The replicator/interactor framework provides two things the raw meme concept lacks:

1. **Level-specificity.** Instead of vaguely saying "memes evolve," Hull's framework requires you to specify: what entity is the replicator? What entity is the interactor? At what level does selection operate? This disciplines the analysis.

2. **Mechanism-specificity.** Instead of saying "memes spread because they're fit," Hull's framework requires you to identify the *interaction* that generates differential replication. What selective environment is the interactor engaging? What counts as success?

### Example: Religious Ideas

Using Hull's framework to analyze the spread of religious ideas:

| Component | Identification |
|-----------|---------------|
| Replicator | Specific doctrinal propositions, ritual scripts, theological arguments |
| Interactor | Religious community, congregation, denomination |
| Selective environment | Competition for adherents, political/social context, psychological needs |
| Selection mechanism | Interactors that attract and retain adherents propagate their replicators; others decline |
| Fitness (replicator) | How many communities adopt this doctrine / ritual |
| Fitness (interactor) | How many adherents the community sustains over time |

This is more analytically productive than simply saying "religious memes spread well."

## Application to the Engram System

Hull's framework maps cleanly to the agent-memory system:

### The Mapping

| Hull's framework | Engram system |
|-----------------|--------------|
| **Replicator** | Knowledge file content — the text/ideas that get loaded into context and influence agent output |
| **Interactor** | The agent-in-context — the loaded knowledge plus the agent's processing, which collectively engages the "selective environment" of user interaction |
| **Selective environment** | User feedback, curation decisions, promotion/archival actions |
| **Selection mechanism** | Files that influence useful agent behavior get promoted; files that don't get archived or forgotten |
| **Replicator fitness** | How often a knowledge file is loaded, how much it influences output, whether its content propagates to new files |
| **Interactor fitness** | Whether the agent-in-context (with its loaded knowledge) produces outputs the user values |

### Design Implications

1. **Track replicator lineage.** Hull's framework for scientific credit has an analog: knowledge files should track which other files influenced them (`origin_session`, cross-references). This enables lineage analysis — which ideas are actually propagating through the system?

2. **Separate replicator fitness from interactor fitness.** A knowledge file might be frequently loaded (high replicator fitness) but contribute nothing to useful agent behavior (low interactor fitness). The curation pipeline should be able to distinguish these — access frequency alone is not a sufficient quality signal.

3. **Multiple levels of interactor.** The individual agent session is one interactor, but so is a sequence of sessions addressing a particular topic, and so is the entire agent-user relationship. Selection operates at all these levels — a knowledge file might be useful in a single session but harmful across sessions (reinforcing a bias).

4. **Credit and provenance.** Hull showed that credit tracking is essential for healthy idea-selection in science. In the Engram system, provenance tracking (which file came from where, which session produced it) serves the same function — it enables the user to trace intellectual lineage and detect problematic dynamics (e.g., a single dubious source file influencing dozens of downstream files).

## Key References

- Hull, D.L. (1980). Individuality and selection. *Annual Review of Ecology and Systematics*, 11, 311–332.
- Hull, D.L. (1988). *Science as a Process: An Evolutionary Account of the Social and Conceptual Development of Science*. University of Chicago Press.
- Dawkins, R. (1982). *The Extended Phenotype: The Long Reach of the Gene*. Oxford University Press.
- Plotkin, H. (1994). *Darwin Machines and the Nature of Knowledge*. Harvard University Press.
- Godfrey-Smith, P. (2009). *Darwinian Populations and Natural Selection*. Oxford University Press.
