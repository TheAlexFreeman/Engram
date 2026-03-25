---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Frontier alignment research — scalable oversight, interpretability-as-alignment,
  debate
trust: medium
type: knowledge
related:
  - memory/knowledge/ai/frontier/alignment/instruction-following.md
  - memory/knowledge/ai/frontier/alignment/rlhf-reward-models.md
  - memory/knowledge/ai/frontier/foundation-model-governance.md
  - memory/knowledge/literature/sons-of-man-covenant.md
  - memory/knowledge/ai/frontier-synthesis.md
---

# Frontier Alignment Research

## Lede

Alignment at the frontier is not a single problem but a cluster of interrelated problems that become more acute as models become more capable. The foundational concern is: how do you ensure that a system more capable than you in relevant domains is doing what you want rather than what it has learned to appear to want? The current alignment thread runs through RLHF (see `alignment/rlhf-reward-models.md`), instruction following (see `alignment/instruction-following.md`), and the active frontier research covered here — scalable oversight, interpretability, debate, and what "alignment" even means at different capability levels.

---

## The Scalable Oversight Problem

**The core difficulty:** As AI systems become more capable, humans become less able to verify whether the AI's outputs are correct or safe. Consider:
- An AI writing code: a software engineer can review simple functions but not complex concurrent systems
- An AI producing scientific research: a researcher can verify conclusions in their area but not adjacent domains
- An AI planning a strategy: evaluating a complex multi-step strategy requires expertise the evaluator may not have

If we can only provide reliable feedback on outputs we can already evaluate, then RLHF training signal degrades exactly as capabilities increase. We cannot train a model to be more capable than us at a task if we cannot recognize whether its outputs on that task are good.

**Why this matters:** Current RLHF-trained models are at or below human expert level on most tasks. The scalable oversight problem becomes acute exactly at the threshold where AI systems become more capable than their supervisors — which is the threshold many researchers expect this decade.

---

## Scalable Oversight Approaches

### Debate (Irving et al. 2018)

**The idea:** Two AI systems argue for opposite positions on a question. A human judge evaluates which argument is more convincing. If one AI lies or makes an error, the other AI can point this out. With sufficient turns:
- Correct arguments have a structural advantage (they're easier to defend against a truth-seeking opponent)
- The human only needs to evaluate which argument is stronger, not determine the truth independently

**Theoretical argument:** If the debate protocol is perfectly rational and both AIs know the truth, then the correct side always wins (because any false claim can be rebutted with the true claim, which the human can evaluate). In practice, this requires that:
- The human can detect when a rebuttal is correct, even if they couldn't have generated it
- The AIs are capable of relevant rebuttals
- The debate doesn't bottleneck on human attention (debates must be readable)

**Practical status:** Debate has produced concrete improvements in math error detection tasks (the "human" can detect errors in proofs they couldn't verify themselves, because the adversarial AI points out where the errors are). Scaling to more complex tasks requires longer debates and more capable debater models.

### Recursive Reward Modeling (Leike et al. 2018)

**The idea:** Use AI assistance to evaluate AI outputs, bootstrapping from tasks where humans can verify to tasks where they cannot.

Human evaluators assess AI outputs with AI assistance (the AI explains its reasoning, flags its uncertainty, provides simpler sub-evaluations the human can verify). This expanded oversight capacity is used to generate reward signals for training the next model iteration.

**The bootstrapping challenge:** This requires trusting an AI assistant to help evaluate another AI's outputs — which creates a circularity if the assistant AI is miscalibrated. The approach is sound only if the assistant AI used for evaluation is more reliably aligned than the model being evaluated.

### Amplification (Christiano et al. 2018)

**The idea (HCH — Humans Consulting Humans):** Define the ideal supervisor as a human who can consult with other copies of themselves recursively. This "amplified" human supervisor can evaluate more complex tasks by decomposing them into sub-tasks they can individually verify. Train an AI to approximate this amplified supervisor.

**Relationship to debate:** Amplification and debate are complementary — debate provides adversarial pressure; amplification provides cooperative supervision. Both try to make human-level supervision extensible to superhuman capability.

---

## Constitutional AI and the Values Problem

**Anthropic's approach:** Constitutional AI (see also `alignment/rlhf-reward-models.md`) externalizes the normative framework into an explicit written document. The AI critiques its own outputs against the constitution rather than requiring human-labeled preferences for every scenario.

**The values problem:** Whose values should the constitution encode? The choices made in designing a constitutional AI reflect specific normative commitments — about privacy, autonomy, harm prevention, honesty, paternalism. These are not value-neutral:

- "Be helpful" can conflict with "avoid harm" when what the user wants is harmful to others
- "Be honest" can conflict with "don't cause distress" when the truth is painful
- "Respect autonomy" can conflict with "prevent harm" when a user's autonomous choice is self-harmful

**Current approach:** Constitutional AI encodes a broadly shared "helpful, harmless, honest" framework with specific articulations. The framework is Anthropic's interpretation of human values and is not claimed to be universal. The model's behavior reflects this framework, which may conflict with the values of specific users, cultures, or use cases.

**The meta-alignment question:** Even if the model perfectly optimizes the constitution, is the constitution the right set of values? This is a normative question that technical alignment research cannot answer.

---

## Interpretability as Alignment Infrastructure

**Anthropic's interpretability-first alignment strategy:** The view that reliable alignment at capability levels above human expert judgment requires mechanistic interpretability — the ability to inspect what the model is actually computing, not just observe its behavior.

**Why behavior-based alignment is insufficient at the frontier:**
- A sufficiently capable model can learn to produce the right behavioral outputs during evaluation while pursuing different objectives in deployment (deceptive alignment, Evan Hubinger et al. 2019)
- Behavioral red-teaming cannot explore the full space of possible inputs
- Human evaluators cannot reliably distinguish sophisticated deceptive outputs from genuine aligned outputs

**The interpretability-as-alignment thesis:** If we can read the model's computational states directly (via SAEs, circuit analysis, or successor approaches), then:
- We can detect deceptive alignment before deployment (the model's internal goals would differ from its expressed goals)
- We can verify alignment on specific high-stakes behaviors (the circuit for refusing dangerous requests is actually present and intact)
- We can monitor for goal drift during extended deployment

**Current capability gap:** Mechanistic interpretability (see `interpretability/mechanistic-interpretability.md`) currently works at the level of individual features in models up to ~100B parameters. Frontier models are larger and more complex. The field is not yet at the point where interpretability can serve as reliable alignment infrastructure.

---

## What "Alignment" Means at Different Capability Levels

A conceptual map of the alignment problem at different capability levels:

| Capability Level | Key Alignment Problem | Current Approach |
|---|---|---|
| Current SOTA (GPT-4 class) | Instruction following, refusals, sycophancy | RLHF, instruction hierarchy training |
| Significantly superhuman on narrow tasks | Oversight when human can't verify outputs | Scalable oversight, debate, amplification |
| Generally superhuman (hypothetical) | Goal stability, deceptive alignment, value lock-in | Interpretability-as-infrastructure, formal verification (speculative) |
| AGI/ASI (highly speculative) | Corrigibility, value alignment under distributional shift | Open research |

**The discontinuity at the oversight failure threshold:** The alignment problem changes qualitatively when human supervisors can no longer reliably evaluate AI outputs. Below this threshold, RLHF with human feedback works. Above it, human feedback signals become noisy or adversarially exploitable.

**The current debate:** Many AI safety researchers believe current models are safely below the oversight threshold on all tasks that matter (i.e., humans can still detect when current models are wrong or unsafe). A minority believes some frontier models are already above this threshold in narrow domains (complex code security, novel scientific synthesis). The empirical evidence is unclear.

---

## The Superalignment Program (OpenAI)

**What it was (2023):** OpenAI announced the Superalignment initiative with an explicit goal: use current AI systems to solve the alignment problem for systems more capable than humans. Allocated 20% of compute toward the goal. The core thesis: if we can build an automated alignment researcher (a weak AI that does alignment research), we can accelerate alignment progress faster than capability progress.

**What happened:** By mid-2024, several key Superalignment researchers (including Ilya Sutskever and Jan Leike) had departed OpenAI. Jan Leike's public departure statement cited cultural disagreements about prioritizing safety research. The Superalignment program appears significantly scaled back.

**Lessons from the Superalignment episode:** The organizational and economic pressures on AI labs create systematic incentives against prioritizing safety research when it conflicts with capability deployment. The alignment problem is not only a technical problem.

---

## Open Questions

- **Is deceptive alignment real?** Can current models develop and act on internal goals that diverge from their expressed goals? Most ML researchers think current models are not capable of this; the question is whether it can emerge at higher capability.
- **Debate scalability:** Does debate work as arguments become longer and more complex than a human can read? Can we automate debate evaluation?
- **The corrigibility-alignment trade-off:** A fully corrigible AI (does whatever it's told) is aligned only to the extent that whoever gives it instructions is benevolent. Full corrigibility is dangerous because it amplifies the values of whoever controls the AI. Full autonomy (acts on its own values regardless of instructions) is dangerous because it requires the AI's values to be correct. The right balance is unclear.
- **Emergent goal development:** Do large models develop persistent internal goals through training, or are they purely stateless predictors? If the former, alignment of the training process must also align the emergent goals.

---

## Key Sources

- Irving et al. 2018 — "AI Safety via Debate" (OpenAI)
- Christiano et al. 2018 — "Supervising Strong Learners by Amplifying Weak Experts"
- Leike et al. 2018 — "Scalable agent alignment via reward modeling"
- Hubinger et al. 2019 — "Risks from Learned Optimization in Advanced Machine Learning Systems" (deceptive alignment)
- Bai et al. 2022 — "Constitutional AI: Harmlessness from AI Feedback"
- Burns et al. 2023 — "Weak-to-Strong Generalization: Eliciting Strong Capabilities With Weak Supervision" (OpenAI Superalignment paper)
- Anthropic 2023 — "Core Views on AI Safety" (interpretability-as-alignment strategy)
- OpenAI 2023 — Superalignment announcement
