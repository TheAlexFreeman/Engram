---
created: '2026-03-20'
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: medium
related: blackmore-meme-machine.md, ../../rationalist-community/ai-discourse/industry-influence/concept-migration-rlhf-constitutional-ai-evals.md, idea-fitness-vs-truth.md, hull-replicator-interactor.md
---

# Dawkins and the Meme Concept

## The Original Proposal

In the final chapter of *The Selfish Gene* (1976), Richard Dawkins introduced the concept of the **meme** — a unit of cultural transmission that undergoes variation, selection, and replication, analogous to the gene in biological evolution. The chapter was almost an afterthought; it has become one of the most influential (and most contested) ideas in the study of culture.

### The Argument

Dawkins's core argument was about **universality of Darwinism**, not about culture specifically. Any system that has:

1. **Replication** — entities that make copies of themselves
2. **Variation** — copies are imperfect; mutations arise
3. **Differential fitness** — some variants replicate more successfully than others

...will undergo evolution by natural selection. Genes are One such system. But the logic is not gene-specific. If cultural units exist that satisfy these three properties, cultural evolution is inevitable.

### The Term

"Meme" was coined from the Greek *mimeme* (that which is imitated), shortened to rhyme with "gene." Dawkins offered examples: tunes, ideas, catch-phrases, clothes fashions, ways of making pots. A meme propagates by "leaping from brain to brain via a process which, in the broad sense, can be called imitation."

### Replicator Properties

Dawkins specified three properties that determine a replicator's evolutionary success:

| Property | Definition | Meme example |
|----------|-----------|-------------|
| **Fidelity** | Accuracy of copying | A mathematical proof copies with high fidelity; a rumor does not |
| **Fecundity** | Rate of replication | A catchy tune spreads faster than a complex philosophical argument |
| **Longevity** | Duration of survival in any given copy | Written ideas survive longer than spoken ideas |

The interaction of these properties determines which memes will dominate the "meme pool" — the cultural analog of the gene pool.

## Dennett's Extension: Memes as Mind Parasites

Daniel Dennett (*Darwin's Dangerous Idea*, 1995; *Breaking the Spell*, 2006) developed the meme concept in a direction Dawkins only hinted at: memes as **parasites** that use human minds as hosts, spreading in ways that need not benefit — and may actively harm — their hosts.

### The Parasite Model

Just as a virus uses cellular machinery to replicate without benefiting the cell, a meme can use cognitive machinery to replicate without benefiting the thinker:

- **Religious memes:** "Believe this or suffer eternal punishment" is a meme that includes its own transmission mechanism (threat of punishment for non-transmission) and immune defense (punishment for doubt). It spreads because of its memetic fitness, regardless of whether the belief is true or beneficial.
- **Conspiracy theories:** "They don't want you to know this" is a meme that recruits the skeptic's own critical faculties — any evidence against the conspiracy is reinterpreted as evidence *for* it (cover-up), making the meme resistant to falsification.
- **Nationalism:** National identity memes generate extreme loyalty (willingness to die for the nation) which benefits the meme's propagation (the nation survives) while potentially harming the host (the individual dies).

### The Intentional Stance Toward Memes

Dennett argued that it is useful to adopt the "intentional stance" toward memes — treating them *as if* they have interests (spreading, surviving, resisting competitors), even though they are not conscious agents. This is the same interpretive strategy that Dawkins uses for "selfish" genes: the gene doesn't literally want to replicate, but it behaves as if it does, and this framing generates correct predictions.

## Critiques

### The Unit Problem

The most persistent critique: **what, exactly, is a meme?** In biology, the gene is (approximately) a segment of DNA that codes for a protein. There is no equivalent physical instantiation for a meme.

- Is "democracy" a single meme or a complex of hundreds of memes?
- Is a chord progression a meme? A whole song? A genre?
- When I teach you a word, is the meme the phonological form, the meaning, or the usage pattern?

The vagueness of the unit makes memetics hard to operationalize. Critics (Sperber, Aunger, Bloch) argue that cultural transmission is fundamentally different from genetic transmission: ideas are *transformed* in transmission, not copied. When I tell you a story, you reconstruct it — you don't receive a bit-for-bit copy. This challenges the "replication" requirement.

### The Fidelity Problem

Gene replication has extraordinarily high fidelity (~1 error per 10⁹ bases per replication). Cultural transmission is noisy. A telephone-game experiment shows rapid degradation over a few transmissions. If memes copy with such low fidelity, can they sustain the cumulative selection that makes evolution possible?

Responses:
- **Sperber's epidemiological alternative:** Ideas spread not by high-fidelity copying but by *reconstruction toward cognitive attractors*. We recreate ideas in forms that fit our cognitive biases, not by copying them. This explains cultural stability without requiring high-fidelity copying.
- **Henrich and Boyd's response:** Cultural evolution doesn't require gene-level fidelity. It requires *sufficient* fidelity for cumulative selection, and humans achieve this through explicit teaching, institutional preservation (books, laws), and conformity bias. The printing press dramatically increased memetic fidelity; the internet did so again.

### The Adaptationism Critique

Do memes actually undergo *selection*, or do they simply drift? If cultural change is primarily random (neutral drift), the Darwinian framework is unnecessary. The response: clear examples of selection exist — the spread of effective agricultural techniques, the adoption of better weapons, the preferential transmission of entertaining stories. But the selection mechanisms are diverse (cognitive biases, institutional incentives, ecological fit) and not reducible to a single fitness function.

## The Meme Concept as Productive vs. Pernicious

### Productive uses

- **Framework for cultural dynamics.** Even if "meme" is vague as a technical unit, the *conceptual framework* — variation, selection, transmission, fitness — produces useful analyses of cultural change.
- **Memetic security analysis.** The Engram memetic-security research uses the meme framework productively: treating context-window content as cultural units that can undergo selection, drift, and parasitic exploitation.
- **Interface between biology and culture.** The gene-meme parallel invites rigorous comparison of transmission mechanisms, fitness landscapes, and evolutionary dynamics across biological and cultural domains.

### Pernicious uses

- **False precision.** Treating "memes" as discrete, countable units when the phenomenon is continuous and multidimensional.
- **Genetic analogy overreach.** Importing biological evolutionary concepts (fitness landscape, neutral drift, speciation) without checking whether they apply to cultural transmission.
- **Determinism.** "Memes made me do it" — treating cultural influence as mechanistic causation, erasing human agency and responsibility.

The most productive use of the meme concept is as a **heuristic** — a way of thinking about cultural transmission that generates hypotheses and organizes observations — rather than as a precise scientific theory with countable units and measurable fitness values.

## Implications for the Engram System

1. **The memory system is a meme transmission medium.** Files in the knowledge base are memes (or memeplexes) that undergo transmission (loaded into agent context), variation (reconstructed in new sessions), and selection (curated, promoted, or archived). The Darwinian framework is genuinely applicable here, not merely metaphorical.

2. **Fitness ≠ truth.** A knowledge file's "fitness" in the Engram system (how often it's loaded, how much it influences behavior, whether it gets promoted) does not guarantee its accuracy. Content-biased transmission (compelling writing), prestige-biased transmission (associated with successful sessions), and longevity (early files have more exposure) all influence fitness independently of truth value.

3. **The fidelity question applies.** When the agent loads a file, processes it in context, and writes a SUMMARY entry, the original content is transformed — reconstructed through the lens of the current session. This is the low-fidelity transmission that critics of memetics emphasize. The mitigation is the same as Henrich's response: institutional preservation (git commit history, immutable original files) provides the fidelity that human/agent cognition does not.

## Key References

- Dawkins, R. (1976). *The Selfish Gene* (ch. 11: Memes: the new replicators). Oxford University Press.
- Dennett, D.C. (1995). *Darwin's Dangerous Idea: Evolution and the Meanings of Life*. Simon & Schuster.
- Dennett, D.C. (2006). *Breaking the Spell: Religion as a Natural Phenomenon*. Viking.
- Sperber, D. (1996). *Explaining Culture: A Naturalistic Approach*. Blackwell.
- Aunger, R. (2002). *The Electric Meme: A New Theory of How We Think*. Free Press.
- Bloch, M. (2000). A well-disposed social anthropologist's problems with memes. In R. Aunger (Ed.), *Darwinizing Culture* (pp. 189–203). Oxford University Press.