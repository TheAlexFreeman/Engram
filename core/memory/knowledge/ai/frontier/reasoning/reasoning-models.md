---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Reasoning models — o1, o3, DeepSeek R1, extended thinking
trust: medium
type: knowledge
related: test-time-compute-scaling.md, benchmarking-reasoning.md, ../alignment/rlhf-reward-models.md, ../architectures/state-space-models.md, ../../history/frontier/multimodality-tool-use-and-reasoning-time-compute.md
---

# Reasoning Models: o1, o3, DeepSeek R1, and Extended Thinking

## Lede

The shift from "scale pretraining" to "scale inference-time compute" is the most structurally significant development in AI since the transformer. It connects directly to four threads: the scaling thread (test-time compute is a new scaling axis beyond parameters and data), the capabilities-from-self-supervision thread (reasoning emerges partly from training models to generate and evaluate their own extended thoughts), the alignment thread (longer reasoning chains are more auditable — and more gameable), and the dynamical-systems thread (chain-of-thought literally extends the activation trajectory, giving the residual stream more computational depth to work with). Reasoning models are not simply larger or better-trained LLMs; they are architectures that invest inference-time FLOPs differently.

---

## Background: Chain-of-Thought as Emergent Capability

Chain-of-thought (CoT) prompting (Wei et al. 2022) demonstrated that large language models, when shown examples that include intermediate reasoning steps in the output ("Let's think step by step"), dramatically improve on multi-step tasks — arithmetic, commonsense reasoning, symbolic manipulation. The key observations:

1. **Scale threshold:** CoT benefits only appear above roughly 100B parameters. Below that scale, intermediate steps hurt performance (the model generates incoherent intermediate outputs that corrupt the final answer).
2. **Zero-shot CoT:** Simply appending "Let's think step by step" works without few-shot examples once the model is large enough.
3. **The mechanism (hypothesis):** CoT works because generating intermediate tokens gives the model additional forward passes — each output token is an additional layer of computation on top of all previous tokens. Structured reasoning is computation unrolled into the output space.

This is distinct from the model having "more time to think" in a cognitive sense. Mechanistically, generating intermediate tokens means the model's residual stream processes each token in context, and the attention mechanism integrates all previous intermediate results. CoT makes the computation graph deeper by extending it through the output.

---

## OpenAI o1 and o3

### Architecture and Training

OpenAI has not published o1's full architecture, but the behavioral profile strongly suggests:

**Internal chain-of-thought:** The model generates a hidden scratchpad of intermediate reasoning tokens before producing the visible final answer. This scratchpad is trained to contain productive reasoning and is hidden from users in the interface (though it is used in the model's processing).

**Process reward models (PRMs):** Rather than only rewarding correct final answers (outcome reward), PRMs reward individual reasoning steps. A PRM is trained to score each step in a reasoning chain as correct, incorrect, or uncertain. Training the policy against PRM scores encourages step-by-step correctness rather than just final-answer correctness — a crucial distinction for math and code.

**The PRM vs. ORM distinction:**
- **Outcome Reward Model (ORM):** Scores only the final answer. Reward is sparse (only available at end of search). The model can follow any reasoning path to reach the answer.
- **Process Reward Model (PRM):** Scores each step. Reward is dense. The model is incentivized to reason correctly throughout, not just arrive at a correct answer through a wrong path.

PRMs are harder to train because they require step-level supervision — humans or verifiers must label individual reasoning steps, not just final answers. But they are more sample-efficient and produce more reliable reasoning chains.

**Monte Carlo Tree Search (MCTS) at test time:** There is strong evidence (though not confirmed by OpenAI) that o1 uses search over reasoning trajectories at inference time. Rather than greedily generating one chain of thought, the model explores multiple reasoning paths and selects the best one by some evaluation criterion (PRM score, majority vote, or a separate verifier).

**o3:** Extends o1 with more sophisticated search and a larger compute budget. o3 demonstrates that the performance ceiling of test-time compute scaling has not been reached as of 2025 — spending more FLOPs at inference continues to improve performance, following a scaling curve distinct from the pretraining curve.

### Behavioral Profile

What distinguishes o1-class models in practice:
- Strong on structured problem-solving: mathematical proofs, code generation, multi-step logical deduction
- Dramatically better on tasks requiring backtracking and self-correction
- Slower and more expensive than comparable non-reasoning models
- Sometimes weaker than comparable models on tasks that benefit from broad pattern recognition (trivia, creative writing, fast factual lookup) — the overhead of reasoning can actually hurt when the task does not require it
- "Overthinking" failure mode: generates elaborate reasoning for simple questions, sometimes arriving at wrong answers by over-reasoning

---

## DeepSeek R1: Open Replication

DeepSeek-AI (2025) published both the model weights and full training methodology for R1, making it the first reproducible open-weight reasoning model comparable to o1.

### Training Methodology

**Phase 1: Cold-start supervised fine-tuning**
A curated set of long chain-of-thought examples is used to initialize the model's reasoning style. Without this cold-start phase, early GRPO training is unstable — the model generates incoherent outputs before finding productive reasoning patterns.

**Phase 2: GRPO on verifiable tasks**
Group Relative Policy Optimization (see also `alignment/rlhf-reward-models.md`) is applied to math and code tasks where answers can be verified programmatically. The key insight: for these domains, you do not need a learned reward model. The ground truth is the verifier.

Multiple completions are sampled per problem. Within each group, solutions are ranked by correctness. The policy is updated to increase probability of correct solutions relative to the group baseline, normalized by group variance:

$$\mathcal{L}_{GRPO} = -\mathbb{E} \left[ \frac{1}{G} \sum_{i=1}^{G} \min \left( \frac{\pi_\theta(o_i|q)}{\pi_{old}(o_i|q)} \hat{A}_i, \text{clip}\left(\frac{\pi_\theta(o_i|q)}{\pi_{old}(o_i|q)}, 1 \pm \epsilon \right) \hat{A}_i \right) \right]$$

**Phase 3: Rejection sampling + SFT on all domains**
The GRPO-trained model generates many solutions across diverse domains; only the correct and well-reasoned ones are kept. This filtered set is used for a second round of SFT, improving general instruction-following without degrading reasoning.

**Phase 4: GRPO on all domains + helpfulness/safety RLHF**
Final multi-objective training combining reasoning rewards, safety rewards, and human preference signals.

### The Distillation Line

R1's most pragmatically significant contribution: smaller models (7B–70B parameter Qwen and LLaMA foundations) were fine-tuned on R1-generated reasoning traces. The distilled models demonstrate dramatically better reasoning than their base models. This suggests reasoning capability can be transferred from large reasoning models to small ones through trace distillation — lowering the cost of deploying reasoning skill.

### The Emergent "Aha" Moment

DeepSeek reported observing an interesting phase transition during GRPO training: a point where the model spontaneously begins generating self-correction phrases ("Wait, let me reconsider...") and longer reasoning chains. This was not explicitly trained — it emerged from the RL pressure to solve harder problems. This is evidence that extended reasoning and self-correction are learnable capabilities that emerge from outcome pressure, not just from imitating human reasoning traces.

---

## Anthropic Extended Thinking (Claude 3.7)

Claude 3.7's "extended thinking" mode differs from o1-style reasoning in publicly stated architecture:

- The thinking tokens are visible (streamed to the user in the API) rather than hidden
- No explicit claim of MCTS-style search; thinking is described as linear extended scratchpad
- Trained to use thinking time to explore problem structure before committing to an answer
- The model can be configured with a "thinking budget" — maximum tokens allocated to internal reasoning before forced answer generation

**Architectural difference from o1:** o1 appears to use search over multiple trajectories. Claude extended thinking appears to use a single extended trajectory. Whether this distinction reflects different training procedures or just different interface choices is unclear from external evidence.

**When does extended thinking help most?**
- Mathematical tasks with multiple subproblems
- Code tasks requiring integration across many files or constraints
- Tasks requiring multi-step deduction where early mistakes compound
- Planning tasks where upfront exploration reduces downstream errors

**When it doesn't help (or hurts):**
- Factual lookup (the answer is in pretraining, not in reasoning)
- Pattern recognition tasks (the right feature is "just there" in the activations)
- Simple, direct questions where reasoning adds length without accuracy benefit
- Time-sensitive low-latency applications

---

## The Computational Cost Profile

Reasoning model inference is qualitatively different in cost structure:

| Factor | Non-reasoning model | Reasoning model |
|---|---|---|
| Output tokens per query | ~200–1000 | 1000–100,000+ |
| Latency | Low (parallel generation) | High (serial reasoning chain) |
| Cost per query | Low | 10x–100x higher |
| Accuracy on hard tasks | Lower | Significantly higher |

The reasoning token overhead is the primary barrier to deployment at scale. This creates a strong economic incentive for work on "when to reason" — using meta-reasoning to decide when a full reasoning chain is needed vs. when a direct answer suffices.

---

## Open Questions

- **What is actually happening inside the hidden scratchpad?** There is no published mechanistic analysis of o1's hidden reasoning tokens. Are they computing something that could not be computed without them, or is the improvement from the search procedure applied over them?
- **Does extended reasoning compress into capability?** If you train a small model on outputs from a reasoning model with extended thinking, does the small model acquire the capability without the tokens? (Partial yes: R1 distillation shows capability transfer, but not at full quality.)
- **Reasoning scaling ceiling:** Does test-time compute scaling saturate? Preliminary evidence from o3 suggests it doesn't, at least through 2025. But the pretraining scaling debate suggests every scaling axis eventually saturates.
- **Sycophancy in reasoning:** Do reasoning models inherit the sycophancy problem? Models that reason extensively may reason their way to the conclusion the user appears to want — a sophisticated form of sycophancy that mimics genuine reasoning.
- **Reasoning vs. memorization:** On math benchmarks, how much of the improvement is genuine reasoning vs. memorization of problem-type templates? The AMC/AIME improvement is impressive but these problems have distributional fingerprints.

---

## Key Sources

- Wei et al. 2022 — "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
- Kojima et al. 2022 — "Large Language Models are Zero-Shot Reasoners"
- DeepSeek-AI 2025 — "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning"
- OpenAI 2024 — o1 System Card and technical report
- Lightman et al. 2023 — "Let's Verify Step by Step" (PRM training paper, OpenAI)
- Snell et al. 2024 — "Scaling LLM Test-Time Compute Optimally" (see also `reasoning/test-time-compute-scaling.md`)
- Anthropic 2025 — Claude 3.7 extended thinking documentation
