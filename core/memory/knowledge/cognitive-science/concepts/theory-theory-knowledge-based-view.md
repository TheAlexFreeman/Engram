---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: classical-theory-failures.md, exemplar-theory-hybrid-models.md, basic-level-categories-asymmetry.md, concepts-synthesis-agent-implications.md, knowledge-compilation-proceduralization.md
---

# Theory-Theory and the Knowledge-Based View of Concepts

## The Crisis in the Classical and Prototype Traditions

Both the classical theory and prototype theory (with its ad hoc extensions) struggled to explain a central phenomenon: **concepts don't behave as if categories were arbitrary statistical clusters**. People use concept knowledge in systematically *theory-laden* ways.

**Murphy and Medin (1985)** crystallized this problem with a deceptively simple question: why does the concept "things that could save you from drowning" cohere as a category (life preserver, wooden plank, swimming ability, a helicopter above), even though its members share no prominent perceptual features and there is no prototype?

The answer is that it coheres because of a **causal-functional theory** — reasons why things could save you — not because of similarity or shared features. Category membership is evaluated by **coherence with background knowledge**, not feature overlap.

---

## The Theory-Theory: Concepts as Theory-Embedded

**Theory-theory** (also called the "knowledge-based view" or "theory-embedded concepts") holds that:

1. **Concepts are embedded in intuitive theories.** A concept's structure is partly constituted by its inferential relations to other concepts and to causal, functional, and mechanistic knowledge about the domain.
2. **Features are not equal:** Some features are "deep" (causally central, core) and others are "surface" (perceptually salient, correlated). Theory-theory predicts that conceptual decisions (classification, induction, naming) track the deep features, not the perceptual surface.
3. **Category coherence comes from explanation, not similarity.** Members of a natural category cohere because we have causal/theoretical reasons explaining why they share properties, not merely because they do share properties.

**Example:** "Wolves" and "dogs" are perceptually very similar, yet felt to be distinct biological kinds. Conversely, "a catfish" is a fish but looks nothing like many "typical" fish. People's biological kind concepts track what they believe about genetic ancestry, reproductive isolation, evolutionary lineage — not perceptual prototype distance.

---

## Intuitive Theories in Development

**Susan Carey (1985)** demonstrated that children develop increasingly sophisticated **intuitive theories** in domains like biology, physics, and psychology, and that conceptual growth across childhood involves genuine **theory change** (see `conceptual-change-types.md`), not just accretion of new features.

**Core knowledge systems (Spelke et al.):** Very young infants appear to have skeletal innate frameworks for reasoning about:
- Objects (persistence, solidity, cohesion)
- Agents (goal-directedness, rational action)
- Number (approximate magnitude representation)

These are not full theories but "proto-theories" — sensitivity to domain-specific patterns that scaffold later theory construction.

**Naive biology:** Keil (1989) showed that children's concept of "alive" tracks biological criteria (metabolism, growth, reproduction) rather than perceptual criteria (movement, responsiveness) by age 7-10, even before they have received any formal biology instruction. This suggests that children are constructing causal-functional theories about what living things are, not just tracking prototypical features.

**The characteristic-to-defining shift (Keil & Batterman, 1984):** Young children's concepts are characteristic-feature-based (typical properties of the category); older children's and adults' concepts shift toward defining-feature-based (necessary/sufficient properties, especially causal) for artifact and natural kind concepts. The developmental trajectory moves from similarity-based to theory-based.

---

## Essentialism: Categories Have Hidden Natures

**Psychological essentialism** (Medin & Ortony, 1989; Gelman, 2003) is the folk-theoretical belief that:

- Natural categories (living things, materials) have an underlying **essence** — a deep causal structure — that makes them what they are and explains their surface properties.
- Essences are often unknown but assumed to exist. You may not know *why* robins fly and lay eggs, but you assume there is some biological essence (genetic structure, DNA) that explains it.
- **Categorical induction is essence-based:** If told that all members of one tribe have 60% hematocrit blood, people project this to all members of the tribe (biological essence) but not to members of another tribe (different essence), even if the two tribes are perceptually indistinguishable.

Psychological essentialism is not a literal belief in metaphysical essences — it's a **cognitive placeholder** (Medin & Ortony): people believe that essences exist even when they cannot identify them, and this belief structures category use.

---

## Expert vs. Novice Conceptual Organization

Theory-theory correctly predicts that experts and novices organize the same domain differently, because they have different theories:

**Chi, Feltovich, & Glaser (1981) — physics problem classification:**
- *Novices* group physics problems by surface features (inclined plane problems, pulley problems, spring problems).
- *Experts* group physics problems by deep principles (conservation of energy problems, Newton's second law problems).

This is not a matter of having more features but of having a different theory that specifies which features are causally relevant. Expertise = deeper, more accurate intuitive theory.

**Biological expertise and basic level shift:** For biological experts, the basic level (most informative level) shifts down the hierarchy. A mycologist's basic level for mushrooms is at the species level, where novices would operate at the "mushroom" level. The expert's richer theory generates more informativeness at finer grain sizes.

---

## Implications for Structured Knowledge Bases

**Theory-theory insight for knowledge file design:**

The lesson is that filing concepts by perceptual similarity or string-matching taxonomy misses what is cognitively most important. A knowledge base organized by **causal and functional relations** is more useful than one organized by surface topical similarity.

**Cross-reference as theory-instantiation:** When a file in `knowledge/cognitive-science/metacognition/` cross-references a file in `knowledge/cognitive-science/concepts/` via a causal mechanism (e.g., "source monitoring failures explain why conceptual change is harder than accretion"), that cross-reference is theory-theory-compliant: it encodes a causal relationship, not a surface topical overlap.

**Gärdenfors' geometric model** (see `gardenfors-conceptual-spaces.md`) provides a formal handle for the spatial structure of conceptual spaces, but theory-theory reminds us that the dimensions of those spaces are not arbitrary: the most important dimensions are those that correspond to causally central features as determined by background theories.

**Categorization of knowledge files:** When deciding whether a new knowledge file belongs to `cognitive-science/` vs. `philosophy/`, the theory-theory approach says: consult the causal/explanatory relations in the file. If the file's core claims are explained by and explain other cognitive-science claims (mechanism, prediction, experimental evidence), it belongs in cognitive-science. If its core claims are logical/conceptual/normative, it belongs in philosophy.
