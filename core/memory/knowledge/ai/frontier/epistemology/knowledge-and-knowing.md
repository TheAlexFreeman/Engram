---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: What it means for a model to "know" something — dispositional knowledge, Chinese
  Room, stochastic parrots, world models, grounding
trust: medium
type: knowledge
related: ../../../social-science/sociology-of-knowledge/mannheim-sociology-of-knowledge.md, ../../../cognitive-science/concepts/knowledge-compilation-proceduralization.md, ../../../cognitive-science/concepts/theory-theory-knowledge-based-view.md
---

# What Does It Mean for a Model to "Know" Something?

## Lede

The question of machine knowledge is not peripheral to AI development — it bears directly on capability evaluation (what does a benchmark score mean?), on safety (does the model "know" it is being evaluated?), and on deployment decisions (should we trust the model's output in this domain?). Modern language models' epistemic status is genuinely contested: their pattern-matching range across practically every domain of human knowledge, yet they confabulate, fail systematic generalization tasks, and show competence profiles no human expert exhibits. This note situates the question at the intersection of philosophy of mind, NLP empirics, and practical epistemology.

---

## The Conceptual Landscape

### Knowledge as Dispositional

The classical philosophical tradition analyzes propositional knowledge as "justified true belief" (JTB). This framework is awkward for machines: justification implies a reasoning process; truth is external to any system's representation; belief implies some form of commitment that machines arguably lack.

**The dispositional alternative:** Knowledge can be analyzed as a stable, context-appropriate pattern of behavior. To know that Paris is the capital of France is to reliably apply this fact correctly in contexts where it is relevant — to answer questions about it, to infer from it, to notice when others assert its negation. On this view, knowledge is not a stored proposition but a learned disposition.

**Applied to LLMs:** Models exhibit dispositions across billions of training examples. Their "knowledge" of many facts is indeed dispositional in this sense — they reliably apply the relevant patterns across diverse contexts. The question is whether dispositions are sufficient for knowledge or whether something else is required.

---

### The Chinese Room

Searle's Chinese Room argument (1980): A person in a room processes Chinese symbols according to a rulebook, producing appropriate Chinese responses, without understanding Chinese. Searle: the room exhibits correct behavioral dispositions without genuine understanding.

**Modern reformulation for LLMs:** A language model processes token sequences according to learned parameters, producing contextually appropriate completions, without (allegedly) understanding language. The rules are not a lookup table but a neural function approximator — but the structural argument is similar.

**The objection to Searle's argument (systems reply):** The person doesn't understand Chinese, but the system as a whole (person + rulebook) might. Understanding, if it exists at all, is a property of the whole system. Searle's reply: what if the person memorizes the rulebook? Then the person plus memorized rules — a unified system — still doesn't seem to understand.

**The argument's force has diminished but not disappeared.** The standard response in cognitive science is that meaning arises from functional organization, not any additional "understanding" substance. But the empirical question — whether LLM functional organization is the right kind — is unsettled.

---

### Stochastic Parrots

Bender et al. (2021) introduced the "stochastic parrot" framing: a very large language model is, in some sense, a very sophisticated pattern matcher on forms (token sequences) without access to the meaning those forms conventionally convey. The model "knows" statistical regularities of word co-occurrence; it does not know what the words refer to.

**The core claim:** Meaning is constituted by grounding in the world (referential relations, causal connections to objects and events). Because LLMs train exclusively on text, they have access only to the relations between forms, not to what the forms refer to. The model can produce a coherent description of "redness" without having any relationship to the color red.

**The empirical complication:** LLMs show striking generalization abilities that seem to exceed pure statistical pattern matching. They solve novel mathematical problems, translate into language pairs with minimal training data, and produce correct inferences in situations absent from their training distribution. This is hard to explain if the model only knows surface patterns.

**The partial vindication of stochastic parrots:** LLMs also show striking failures. They are misled by adversarial reformulations of the same question (if the question is phrased unusually, accuracy drops sharply). They fail systematic tests of logical consistency (affirming Q when asked "If P then Q; P?" but denying P when asked in a different format). These failures suggest something more than surface form is being processed, but less than human-style semantic grounding.

---

### World Models Hypothesis

**The hypothesis:** Despite training on text, sufficiently large LLMs learn internal representations that function as implicit world models — compressed descriptions of reality that allow correct inference to new situations.

**Evidence for:**
- Models generalize to physical reasoning tasks not explicitly represented in training
- GPT-style models trained only on language data show accurate implicit knowledge of spatial relationships (up/down, in front/behind) that would require a world model to generalize correctly
- Otherkin et al. (2023): language models trained on the Othello game transcripts learn to represent game board state internally (verified by probing), even though only move sequences are in the training data

**Evidence against:**
- Systematic failures on "what-if" counterfactual reasoning (models perform near chance on causal intervention questions)
- Failures on abstract reasoning benchmarks with novel symbolic structures (ARC tasks)
- Failures on tests of physical intuition that are well-specified in language but require spatial simulation

**A synthesis:** Models likely learn partial, domain-specific world models that generalize within the domains well-represented in their training data, but lack the unified, causally structured world model that humans construct through embodied experience across dozens of modalities.

---

### Distributional Semantics and Its Limits

**Distributional semantics** (Harris 1954): meaning is constituted by co-occurrence patterns across contexts. "A word is characterized by the company it keeps" (Firth 1957). Vector representations like word2vec, GloVe, and transformer contextualized embeddings can be understood as extremely sophisticated implementations of distributional semantics.

**What distributional semantics captures:**
- Synonym and antonym relations (symmetric vs. asymmetric co-occurrence patterns)
- Semantic field membership (diseases co-occur with symptoms; tools co-occur with tasks)
- Analogical relations ("man is to woman as king is to queen" — captured by linear vector arithmetic in well-trained embeddings)

**What distributional semantics cannot capture:**
- **Reference:** which specific object in the world a noun phrase refers to — text alone underdetermines this
- **Causal structure:** which event causes which; causation is not reliably signaled by word order or co-occurrence
- **Modality-specific content:** what red looks like, what cold feels like — these cannot be inferred from text-to-text regularities

**The practical implication:** Distributional semantics is sufficient to produce outputs that are statistically appropriate across a wide range of contexts, but it systematically fails for tasks that require reference, causation, or modality-specific content — which includes many scientifically and operationally important tasks.

---

## Grounding and Embodiment

**The grounding problem (Harnad 1990):** Symbolic systems (including language) get their meaning from connections to the non-symbolic world. A dictionary defines words using other words: the definition of "red" includes "wavelengths between 620–750 nm," which requires knowing what wavelength is, which requires knowing what light is... The chain of definition terminates only when symbols are grounded in something non-symbolic (perception, action). LLMs have no such termination.

**Weak grounding via multimodal training:** GPT-4V, Claude Claude 3, and similar models are trained on image-text pairs. This provides some grounding: the model learns associations between visual patterns and word tokens. Empirically, multimodal models show improved spatial reasoning and reduced confabulation on visual tasks. But this grounding is still indirect (image-to-token, not image-to-action).

**Strong grounding (embodied AI thesis):** True grounding requires sensorimotor loops — the ability to act on the world and observe the consequences. This is the standard condition of human knowledge from birth: we learn object permanence by tracking objects across occlusion; we learn causality by manipulating objects; we learn language in contexts where the language refers to things we are simultaneously experiencing.

**The practical compromise:** For most operational uses, weak grounding (multimodal + broad textual context) is sufficient. For tasks requiring genuine reference-tracking, ground-truth causal understanding, or novel physical reasoning, current LLMs exhibit systematic gaps that argue for human oversight or integration with external tools (code execution, database lookup, calculator).

---

## Open Questions

- **The depth of world models:** Can we characterize, in a domain-general way, which aspects of reality LLMs model successfully vs. fail at? The current evidence is fragmentary and benchmark-specific.
- **Does scale resolve grounding?** Would a model trained on 100× more internet text (or a perfect text record of all human knowledge) approach genuine grounding? Or is textual training fundamentally insufficient regardless of scale?
- **Knowledge vs. skill:** Many model capabilities look more like "skills" (procedural competence) than "knowledge" (propositional representation). Is this distinction meaningful, or is all competence ultimately dispositions?
- **Calibration as an epistemological criterion:** Well-calibrated models "know what they know" — their uncertainty estimates match empirical accuracy. Is calibration a reasonable operationalization of genuine knowledge? It is measurable and practically useful, even if philosophically insufficient.

---

## Key Sources

- Searle 1980 — "Minds, Brains, and Programs" (Chinese Room, Behavioral and Brain Sciences)
- Bender et al. 2021 — "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?"
- Harnad 1990 — "The Symbol Grounding Problem"
- Harris 1954 — "Distributional Structure" (Word)
- Otherkin et al. 2023 — "Emergent World Representations: Exploring a Sequence Model Trained on a Synthetic Task" (actually: Li et al. 2022, "Emergent World Representations")
- Marcus 2018 — "Deep Learning: A Critical Appraisal"
- Mitchell & Krakauer 2023 — "The Debate over Understanding in AI's Large Language Models"
- Gendron et al. 2023 — "Large Language Models Are Not Robust Multiple Choice Selectors" (format sensitivity)
- Rogers, Kovaleva & Rumshisky 2020 — "A Primer in BERTology: What We Know About How BERT Works"