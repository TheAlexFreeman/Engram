---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Emergence and phase transitions in LLMs — grokking, the emergence debate, bitter
  lesson
trust: medium
type: knowledge
related: ../../../mathematics/statistical-mechanics/ising-model-phase-transitions.md, ../../../philosophy/emergence-consciousness-iit.md, mechanistic-interpretability.md
---

# Emergence and Phase Transitions in LLMs

## Lede

"Emergence" — the appearance of qualitatively new capabilities at scale — is simultaneously one of the most discussed and most contested phenomena in AI research. The dynamical-systems thread frames emergence as phase transitions (abrupt qualitative changes in system behavior under continuous parameter variation), which gives it mathematical precision. The epistemology thread asks what a "capability" is and whether apparent emergence reflects genuine discontinuous change or measurement artifacts. The scaling thread grounds the discussion in empirical evidence: some things really do change discontinuously with model size, even if others turn out to be smooth curves made to look sharp by coarse measurement. Getting the emergence story right matters for predicting what future AI systems will be able to do.

---

## The Empirical Claim: Sharp Capability Jumps

**Emergent Abilities (Wei et al. 2022):** This paper compiled dozens of examples where model performance on specific tasks jumps from near-random to near-perfect across a threshold of scale, rather than improving smoothly. Examples:

- **Arithmetic:** Models below ~50B parameters perform at chance on 3-digit addition; above ~100B parameters, performance jumps sharply to near-perfect
- **Truthfulness (TruthfulQA):** Almost no improvement below ~150B parameters; large improvement above
- **Multistep reasoning (BIG-Bench Hard):** Flat performance until large scale
- **Chain-of-thought:** Below ~100B parameters, chain-of-thought reasoning makes performance worse; above, it dramatically improves performance

The paper identified ~137 tasks showing apparently emergent behavior. The implication: capabilities cannot always be predicted by extrapolating from smaller scales; new capabilities may appear suddenly at scale thresholds we have not yet reached.

---

## The Counter-Argument: Measurement Artifacts

**Schaeffer et al. 2023 — "Are Emergent Abilities of Large Language Models a Mirage?":**

The most important challenge to the emergence narrative. The argument:

Many of the "emergent" ability results use **discontinuous metrics** on tasks that have continuous underlying improvement. When you use:
- **Accuracy (pass/fail):** A model's probability of the correct answer may improve smoothly from 0.05 to 0.95 across scale; but if you measure binary accuracy (correct or not), you get 0% until the probability crosses 0.5, then 100%. The discontinuity is in the metric, not the capability.

**The test:** When the same tasks are measured with **continuous metrics** (log probability of the correct answer, rather than binary accuracy), the emergent jumps disappear — performance improves smoothly and predictably with scale.

**The conclusion:** Many "emergent" abilities are artifacts of measuring a continuous underlying process with a threshold metric. The underlying capability scales smoothly; the observed metric creates the illusion of a sharp transition.

**What is NOT explained by the measurement artifact argument:**
- Chain-of-thought: Adding chain-of-thought reasoning actively hurts smaller models (performance below a random baseline is not equivalent to slow improvement). This looks like a genuine phase transition in which CoT switches from harmful to helpful.
- In-context learning: The qualitative shift from "can't learn from examples" to "learns from examples" in the context window may be a genuine transition (Olsson et al.'s induction head analysis supports this: the relevant circuits appear relatively abruptly).

**Current status:** The measurement artifact explanation accounts for many but not all observed emergent phenomena. Some capability discontinuities appear genuine; careful metric design is required to distinguish genuine emergence from metric artifacts.

---

## Grokking: Delayed Generalization

**Grokking (Power et al. 2022, DeepMind):** A phenomenon observed in small transformer models trained on modular arithmetic (e.g., addition modulo 97): the model first memorizes the training data (training accuracy 100%, validation accuracy ~50%) and then, with continued training well past memorization, undergoes a phase transition to true generalization (validation accuracy rapidly approaching 100%).

**The timeline:**
- Early training: loss decreases as model memorizes training examples
- Middle training: training accuracy stabilizes at 100%; validation accuracy flat (~chance)
- Late training: after thousands of additional gradient steps, validation accuracy sharply improves to near-perfect
- The gap between memorization and generalization can be many training steps

**Why this matters:**
1. **Generalization is not apparent during training:** By standard early-stopping criteria (stop when training loss stops decreasing), you would stop training at memorization. You would miss the generalization phase.
2. **Phase transitions in learning:** Grokking provides a clean laboratory example of a genuine phase transition in generalization — not a smooth curve, a sharp qualitative change.
3. **Mechanism:** The model develops two solutions simultaneously — a memorization solution and a general algorithm solution. With continued training, regularization effects (weight decay) favor the more compact general solution, which eventually dominates.

**The circuit story for grokking:** Nanda et al. (2023) traced the specific algorithm that generalizes in modular addition: the model develops Fourier features and uses a specific trigonometric identity. The grokking transition corresponds to the Fourier circuit becoming dominant over the memorization circuits.

**Implication for LLMs:** Whether grokking dynamics apply to large LLM training is unclear — LLMs are not typically trained "beyond memorization" in the same explicit sense. But the principle (generalization may require more training than memorization and may appear suddenly) likely influences the understanding of when capabilities appear during training.

---

## In-Context Learning as an Emergent Capability

**The ICL emergence story:** In-context learning (learning a new task from a few examples in the prompt) appears weakly at ~1B parameters, becomes reliable at ~10B parameters, and scales further with model size. This has the hallmarks of genuine emergence: below a threshold it is essentially absent; above it is highly functional.

**The induction head explanation:** Olsson et al. (2022) traced the emergence of a specific circuit (induction heads) that implements the basic mechanism of in-context learning. This circuit forms relatively abruptly during training — not as a gradual strengthening but as a phase transition in the training dynamics. The formation of the induction head circuit corresponds to a sharp drop in loss that is visible in the training curve.

**Implications:** This supports the view that some emergent capabilities correspond to genuine phase transitions in the learning dynamics — the formation of a new computational circuit — rather than just metric artifacts.

---

## The Bitter Lesson

**Sutton 2019 — "The Bitter Lesson":** The most important lesson of AI research: "general methods that leverage computation are ultimately the most effective, and by a large margin." Specific human-engineered features and domain knowledge consistently lose to scale + simple objective + vast computation.

**The lesson applied:**
- Vision: hand-crafted features (HOG, SIFT) lost to convolutional networks; convolutional network designs lost to ViTs trained at scale
- Language: grammar-based parsing and hand-crafted features lost to n-gram models; n-gram models lost to LSTMs; LSTMs lost to transformers at scale
- Games: hand-crafted evaluation functions lost to self-play deep RL (AlphaGo → AlphaZero)

**Why it's "bitter":** Domain experts invest effort in engineering solutions that turn out to lose to simpler methods with more compute and data. The engineering knowledge does not transfer; the compute-scale approach wins even when the engineering approach seems definitively better in the short term.

**The meta-lesson for emergence:** The bitter lesson predicts that trying to engineer specific capabilities into models (expert systems, knowledge graphs, symbolic reasoning modules) will lose to scale + simple training objective. If a capability appears emergent at scale, the correct response is usually "train bigger" rather than "engineer a solution."

**Limits:** The bitter lesson does not say scale is sufficient for everything — ARC-AGI performance remains stuck despite scale. The limits of the scaling approach are one of the most important open questions.

---

## What "Capability" Actually Means

A deeper question underlying the emergence debate: what is a "capability"?

**Prompt-specificity:** The same underlying model may show a capability in one phrasing and fail in another. "What is 13 × 17?" (likely correct) vs. "In a store, I buy 13 items at $17 each. What is my total?" (less reliable). Is arithmetic a "capability" if it is present only for specific prompt formats?

**Task-generality:** A model fine-tuned on GSM8K (grade-school math word problems) outperforms on GSM8K but may not outperform on novel math problem types. Is "math reasoning" a capability or is "GSM8K-formatted math reasoning" a capability?

**Architecture-dependence:** Some capabilities appear in transformer models at scale but not in other architectures at comparable parameters. Is the capability in the "model" or in the "model-architecture combination"?

**The operationalist position:** A capability is defined relative to a benchmark, a prompt distribution, and an evaluation procedure. Claims about "emerging capabilities" are always relative to a specific measurement framework. There is no architecture-neutral, prompt-neutral notion of capability.

---

## Open Questions

- **Predicting emergent capabilities:** Can we forecast which capabilities will emerge at a given scale before training? Current approaches (scaling law extrapolations) work for smooth curves; phase transitions are unpredictably timed.
- **Emergence in multimodal models:** Do vision-language and audio-language models show different emergence patterns than text-only models? Less studied.
- **Inducing grokking in LLMs:** Can training curricula be designed to induce grokking-style transitions in specific capabilities of large models? Would this accelerate generalization?
- **The bitterness has limits:** For what tasks will engineering and symbolic approaches eventually outperform scale + simple objective? Identifying these cases would be practically and theoretically important.

---

## Key Sources

- Wei et al. 2022 — "Emergent Abilities of Large Language Models"
- Schaeffer et al. 2023 — "Are Emergent Abilities of Large Language Models a Mirage?" (measurement artifact critique)
- Power et al. 2022 — "Grokking: Generalization Beyond Overfitting on Small Algorithmic Datasets"
- Nanda et al. 2023 — "Progress measures for grokking via mechanistic interpretability"
- Olsson et al. 2022 — "In-context Learning and Induction Heads"
- Sutton 2019 — "The Bitter Lesson"
- Chollet 2019 — "On the Measure of Intelligence" (ARC-AGI as anti-emergence-artifact benchmark)
- Srivastava et al. 2022 — "Beyond the Imitation Game" (BIG-Bench, context for emergent ability measurements)