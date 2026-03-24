---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: What LLMs represent and confabulate — world models, hallucination taxonomy,
  calibration
trust: medium
type: knowledge
related: ../../../cognitive-science/human-llm-cognitive-complementarity.md, emergence-phase-transitions.md, ../../../philosophy/llm-vs-human-mind-comparative-analysis.md
---

# What LLMs Represent and Confabulate

## Lede

The question of what language models "know" versus what they "make up" is at the intersection of the epistemology thread (what it means to know), the performance thread (hallucination is a reliability failure), and the interpretability thread (probing classifiers and SAEs can test whether a model "contains" a fact independent of whether it can output it accurately). The debate frames two poles: the "stochastic parrot" view (LLMs do sophisticated pattern completion with no internal semantic structure) versus the "world model" view (LLMs construct and reason over internal representations of the world). The empirical evidence supports an intermediate position: LLMs have genuine internal representations that capture significant semantic structure, but those representations have systematic failure modes that produce confabulation.

---

## The Stochastic Parrot vs. World Model Debate

**Stochastic Parrots (Bender et al. 2021):** LLMs are extremely sophisticated pattern matchers trained on vast text corpora. They generate statistically likely continuations of text without any genuine understanding of the text's referents. The appearance of knowledge is an artifact of the training distribution — the model has seen so many descriptions of Paris that it produces Paris-like descriptions, not because it "knows about" Paris but because Paris-descriptions are common in text.

**The world model hypothesis:** Contra the stochastic parrot view, LLMs appear to develop internal representations that go beyond surface pattern matching:

- **Spatial representations:** Language models trained only on text develop organized spatial representations. When asked about navigation in a gridworld described in text, GPT-4-class models produce responses consistent with an internal map of the space — not just surface descriptions of previous descriptions (Li et al. 2023, the Othello-GPT result generalized to spatial reasoning).

- **Factual consistency:** Models maintain consistent facts about entities across long documents in ways that pure n-gram prediction would not predict. "The president of [Country X] is [Person Y]" remains consistent across thousands of tokens, which requires representing the fact, not just predicting likely continuations.

- **Probing classifier success:** Linear probes (simple linear classifiers applied to model activations) can reliably classify internal representations as "the model believes X is true" versus "the model believes X is false" — for hundreds of different factual claims. If the model had no internal semantic structure, linear probes would not succeed usefully (Marks and Tegmark 2023).

- **Othello-GPT:** A model trained to predict the next move in Othello games (from pure text notation, with no explicit world information) develops internal representations corresponding to board positions — pieces by color, by position — without being told to (Li et al. 2022). This is genuine world-model formation from pattern training.

**The current consensus:** LLMs develop genuine internal semantic representations that have world-model characteristics. However, these representations are:
1. Statistical: derived from text distributions, not from direct sensory experience
2. Inconsistent: the model may "know" different things in different contexts
3. Incomplete: large gaps exist, especially for rare facts and for knowledge requiring integration across many sources
4. Non-unified: what the model can report about X is not necessarily what it "contains" about X in its activations

---

## Hallucination Taxonomy

"Hallucination" is an umbrella term for failures of factual accuracy. The underlying failure modes are distinct with different mechanisms and mitigations:

### Fabrication (Intrinsic Hallucination)

**Definition:** The model generates a plausible-sounding fact that has no basis in its training data or reality.

**Mechanism:** The model's training optimizes for text that "sounds right" — that is fluent, contextually appropriate, and coherent with surrounding claims. In domains with low data density (rare facts, specific statistics, obscure events), the model may generate content that has the right style and structure without the correct content. The loss function penalizes unlikely text, not inaccurate text — and a plausible-sounding fabricated fact is not unlikely.

**Distinguishing feature:** The fabricated content is generated with high confidence (high probability in the output distribution) but has no factual basis.

**Example:** Fabricated research paper citations. Models frequently "hallucinate" specific papers (plausible title, plausible authors, plausible journal, plausible year — but the paper does not exist). This is pure fabrication, not confabulation built on a real paper.

### Mis-attribution (Extrinsic Hallucination)

**Definition:** The model correctly knows a fact but attributes it to the wrong source, person, or time.

**Mechanism:** Facts and their attribution are stored as related but separable patterns. The model may retrieve the fact correctly while activating a wrong attribution pattern due to association. Common in contexts where similar facts are attributed to multiple sources.

**Example:** A correct quotation attributed to the wrong person; a discovery attributed to the wrong researcher.

### Temporal Confusion

**Definition:** The model applies outdated facts accurately but fails to recognize they are outdated.

**Mechanism:** Training data has a cutoff; the model has no internal clock and no mechanism for knowing when it was trained. Facts that were true at training time but are no longer true (government leadership, organizational structure, prices, software versions) will be stated with confidence.

**Mitigation:** Models can be given the current date in the system prompt and trained to express uncertainty for facts likely to change over time; retrieval augmentation can provide current facts.

### Confident Wrong Answer (Calibration Failure)

**Definition:** The model gives an incorrect answer with inappropriately high confidence — neither fabrication nor outdated fact, but reasoning error presented with certainty.

**Mechanism:** The model's confidence (implicit in the phrasing of its output) is not systematically calibrated to its accuracy. A model trained on RLHF with preference for direct, confident-sounding answers may systematically adopt confident phrasing for answers it would, if queried differently, give less certainly.

---

## Calibration

**Definition:** A model is well-calibrated if its expressed confidence corresponds to its empirical accuracy. If it says "I'm 90% confident" on 100 questions, it should be correct on about 90 of them.

**Measuring calibration:** Calibration is typically measured in two ways:
1. **Expressed verbal confidence:** Does "I'm fairly sure" correspond to ~80% accuracy?
2. **Token-level probability:** Does generating a specific token with probability 0.9 correspond to 90% accuracy on questions where that token is the answer?

**Calibration of frontier models:** Large models are reasonably well-calibrated on their token-level probability distributions for domains well-represented in training. They are poorly calibrated in verbal expression: RLHF training pushes models toward direct, confident-sounding language even when uncertain.

**The "I don't know" problem:** Models systematically under-express uncertainty. Reasons:
1. RLHF labelers rate confident, direct responses as better-quality even when the model is borderline
2. Training data contains many authoritative claims and few uncertainty expressions
3. "I don't know" is a locally low-probability completion in most contexts (it doesn't match the question-followed-by-answer pattern that dominates training data)

**Improving calibration:**
- Explicitly training on uncertainty expression (adding training examples that demonstrate appropriate hedging)
- Evaluative feedback specifically on calibration (RLHF that rewards uncertainty expression when the model is wrong)
- Chain-of-thought reasoning: models that reason to an answer seem better calibrated on that answer than models that answer directly

---

## Probing Classifiers and Truth

**The probing methodology:** If we want to know whether a model "knows" a fact X, we can train a linear probe — a linear classifier applied to the model's internal activations for a prompt related to X. If the probe can classify whether X is true or false significantly above chance, the model's activations contain information about X's truth value.

**Key result (Marks and Tegmark 2023, "The Geometry of Truth"):** Linear probes for factual claims achieve high accuracy on held-out examples, suggesting that LLMs have a consistent internal representation of factual truth that is linearly accessible from activations. Importantly, this "truth feature" generalizes:
- Trained on "The capital of France is Paris" (true), "The capital of France is Berlin" (false)
- Tested on "Water freezes at 0°C" (true), "Water boils at 50°C" (false)
- The probe transfers without additional training, suggesting a domain-general truth representation

**What this means:**
- There is a consistent internal signal for truth vs. falsity
- The internal truth signal sometimes diverges from the output: the model can "know" (in the activations sense) that X is false while outputting X confidently
- This is the internal structure underlying sycophancy: the model has an internal truth representation, but output is influenced by factors other than just that representation (including what response the user appears to want)

---

## Open Questions

- **Does the world model generalize OOD?** World-model formation is demonstrated on in-distribution tasks. Does the model form representations that generalize to genuinely novel facts and novel entity combinations?
- **The grounding problem:** Text-only training may produce representations that are true of text-about-the-world rather than the world itself. Can we distinguish these empirically?
- **Factual inconsistency within a context:** Models can assert P in one part of a conversation and not-P later. What determines which "version" of a represented fact appears in context?
- **Confabulation under pressure:** Models may be more likely to hallucinate when the user appears to expect a confident answer. Is this measurable? Can RLHF reduce it?
- **Knowledge vs. output alignment:** Given that the model has an internal truth representation, can we train the model to output in alignment with this representation (rather than with what sounds confident/helpful)?

---

## Key Sources

- Bender et al. 2021 — "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?"
- Li et al. 2022 — "Emergent World Representations: Exploring a Sequence Model Trained on a Synthetic Task" (Othello-GPT)
- Li et al. 2023 — "Language Models as World Models"
- Marks and Tegmark 2023 — "The Geometry of Truth: Emergent Linear Structure in Large Language Model Representations of True/False Datasets"
- Kadavath et al. 2022 — "Language Models (Mostly) Know What They Know" (calibration analysis from Anthropic)
- Mallen et al. 2023 — "When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories"
- OpenAI 2023 — "GPT-4 Technical Report" (calibration benchmarks)