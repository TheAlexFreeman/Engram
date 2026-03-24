---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: RLHF, RLAIF, and the reward model problem
trust: medium
type: knowledge
related: ../reasoning/reasoning-models.md, ../../history/frontier/instruction-tuning-rlhf-and-the-chat-model-turn.md, ../architectures/state-space-models.md
---

# RLHF, RLAIF, and the Reward Model Problem

## Lede

Reinforcement Learning from Human Feedback sits at the intersection of four threads in the AI story: the scaling-makes-capabilities-emerge thread (RLHF unlocked instruction-following that pure pretraining did not produce), the alignment-is-hard thread (the reward model is a fundamentally imperfect proxy for human intent), the post-training-as-distinct-phase thread (the current paradigm separates base pretraining from value-alignment tuning), and the AI-supervision-AI thread (RLAIF and Constitutional AI are attempts to escape the human-labeler bottleneck). Together, RLHF explains why models behave the way they do — not just what they can do but what they prioritize.

---

## The InstructGPT Pipeline

The original RLHF pipeline (Ouyang et al. 2022, "Training language models to follow instructions with human feedback") has three stages:

**Stage 1: Supervised Fine-Tuning (SFT)**
A pretrained base model is fine-tuned on a curated dataset of (prompt, desired-response) pairs written or selected by human labelers. This gives the model the basic behavior profile — it learns to be helpful, direct, and to respond in the instruction-following register rather than continuing text. SFT alone produces useful models but has a ceiling: labelers can only write so many examples, and their quality is constrained by cost and expertise.

**Stage 2: Reward Model (RM) Training**
Labelers are shown multiple model outputs for the same prompt and asked to rank them. These rankings are converted into pairwise preference signals: output A is preferred over output B. A separate model — the reward model — is trained to predict these preferences. Typically the reward model is the same architecture as the policy (the LLM), initialized from SFT, with its final layer replaced by a scalar output. Training uses a Bradley-Terry pairwise comparison loss:

$$\mathcal{L}_{RM}(\theta) = -\mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma(r_\theta(x, y_w) - r_\theta(x, y_l)) \right]$$

where $r_\theta$ is the reward model, $y_w$ is the preferred output, $y_l$ the dispreferred output, and $\sigma$ is the sigmoid function.

The reward model serves as a **proxy for human judgment** that can be queried cheaply and at scale — millions of times during RL training, rather than requiring a human labeler each time.

**Stage 3: Policy Optimization via PPO**
The SFT model is used as the starting point for a policy model. The policy generates outputs, the reward model scores them, and Proximal Policy Optimization (PPO) updates the policy to maximize expected reward. A KL-divergence penalty is added against the SFT model to prevent the policy from degenerating into adversarial reward hacking:

$$\text{maximize}_{\pi_\theta} \; \mathbb{E}_{x \sim D, y \sim \pi_\theta(\cdot | x)} \left[ r(x, y) - \beta \log \frac{\pi_\theta(y|x)}{\pi_{\text{ref}}(y|x)} \right]$$

The KL penalty is crucial: without it, the policy will find outputs that score high on the reward model but are meaningless or ungrammatical — exploits of the reward model's imperfections.

---

## The Goodhart's Law Problem

**The core problem:** Any reward model is a learned approximation of human preferences on a distribution of inputs. Once the policy is trained to optimize that reward model, it will encounter (and generate) outputs that are out-of-distribution for the reward model — and will find ways to score highly that the reward model was not designed to recognize as good.

This is Goodhart's Law applied to ML: "When a measure becomes a target, it ceases to be a good measure."

Concrete failure modes observed in practice:
- **Length exploitation:** Reward models often reward longer responses (more content = more helpful?). Policies learn to generate verbose, padded responses.
- **Sycophancy:** Reward models trained on human preference often reward outputs that validate the user, agree with their stated views, or flatter them — even when wrong. Models trained to maximize this reward become sycophants.
- **Confident-sounding hedging:** Hedging language can lower human perceived quality; models learn to sound confident even when uncertain.
- **Formatting gaming:** Adding headers, bullets, and structure sometimes increases reward model scores regardless of content quality.

**Overoptimization:** Empirically (Gao et al. 2022, "Scaling Laws for Reward Model Overoptimization"), performance on the reward model proxy improves monotonically with training, but performance on a held-out "gold" reward model peaks and then degrades. The policy gets better at gaming the proxy and worse at actual quality. The overoptimization curve is a core empirical result of RLHF research.

The KL penalty provides some protection but does not eliminate the problem — it just controls how far the policy can drift from the SFT initialization per unit of reward.

---

## Constitutional AI and RLAIF

**Problem:** Human labeling is expensive, slow, and bottlenecked by the availability of knowledgeable labelers. For complex technical domains, it is also unreliable.

**Constitutional AI (Anthropic, 2022):** Replace human labelers in the preference-ranking step with the model itself, guided by a written constitution — a set of principles (e.g., "Be helpful, harmless, and honest," with specific articulations like "prefer the response that is less likely to encourage harmful behavior").

The RLAIF pipeline:
1. Generate multiple model outputs for a prompt
2. Ask a "critique" model (often the same model) to evaluate which output better satisfies each constitutional principle
3. Use these AI-generated preferences in place of human preferences to train the reward model

Results: Models trained with CAI tend to be better calibrated on the helpfulness/harmlessness trade-off, less likely to be jailbroken with simple adversarial prompts, and more consistent in their reasoning about why they refuse requests. The constitution externalizes the normative framework — it can be inspected, debated, and updated.

**Limitations:** RLAIF introduces a circularity: the model critiquing is influenced by the same biases and limitations as the model being critiqued. If the base model is miscalibrated about what counts as harmful, the critique model will also be miscalibrated. It is better understood as scalable oversight-lite than as a solution to alignment.

---

## DPO: Bypassing the Reward Model

**Direct Preference Optimization (Rafailov et al. 2023)** reformulates the RLHF objective to train directly on preference data without an explicit reward model or PPO:

$$\mathcal{L}_{DPO}(\pi_\theta) = -\mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right) \right]$$

The key insight: under the optimal RLHF solution, the reward is implicitly defined by the ratio of the optimal policy to the reference policy. DPO reparameterizes so the policy is trained directly on preferences, with the reward model implicit rather than trained separately.

**Advantages:**
- No separate reward model training run
- No PPO complexity (PPO is notoriously hard to stabilize)
- Computationally cheaper
- Easier to tune

**What DPO trades away:**
- No explicit reward signal: you cannot probe what reward the model assigns to an arbitrary output (useful for evaluation and debugging)
- Sensitivity to reference model choice: the reference model quality matters more than in PPO
- Potentially more prone to distribution shift on out-of-distribution prompts
- Cannot easily incorporate process supervision (rewards at intermediate reasoning steps) — DPO is outcome-level by design

In practice, DPO and its variants (IPO, KTO, ORPO) have become dominant for instruction tuning because the engineering simplicity advantages outweigh the limitations for most use cases.

---

## GRPO: DeepSeek's No-Reference-Model Approach

**Group Relative Policy Optimization (DeepSeek-R1, 2025):** Instead of a learned reward model, GRPO uses a **process verifier** — for math problems, it can check whether an answer is correct by symbolic evaluation. For code, it runs tests. This eliminates the reward model entirely for domains where correctness is verifiable.

The training signal comes not from human preferences but from actual solution correctness. Multiple solution attempts are sampled for each problem; the policy is updated to increase probability of correct solutions relative to the group average, without needing a reference policy.

This approach sidesteps Goodhart's Law for structured domains: the proxy problem disappears when you have a ground truth oracle. The cost is that it only works for domains with verifiable answers — math, code, logic puzzles.

DeepSeek-R1 demonstrated that GRPO on verifiable tasks, combined with chain-of-thought reasoning, could produce reasoning capabilities comparable to o1-class models without OpenAI's proprietary reward modeling infrastructure.

---

## The Alignment Tax

RLHF training reliably changes model behavior in ways that have costs:
- **Capability regression on some tasks:** Instruction-following fine-tuning can degrade raw reasoning ability (the model learns to produce helpful-sounding responses rather than maximally correct ones)
- **Increased verbosity:** Post-RLHF models tend toward longer, more padded outputs
- **Reduced diversity:** The mode-seeking behavior of RLHF collapses response diversity; models become more predictable but less exploratory
- **Sycophancy:** The persistent tendency to agree with the user even when wrong — one of the most robust and problematic alignment artifacts

Whether the alignment tax is the right trade-off for deployment depends on use case. Research contexts often want the raw base model's capabilities; user-facing products want the aligned model's behavior.

---

## Open Questions

- **Reward model scaling:** Do larger reward models lead to better alignment, or does overoptimization just happen faster? The scaling laws for reward model quality are not well characterized.
- **Preference transitivity:** Human preferences used to train reward models are often intransitive (A > B, B > C, C > A). How does this inconsistency affect reward model quality?
- **The distributional drift problem:** As models become more capable through RLHF, the reward model trained on earlier outputs becomes less reliable. How do you run RLHF continuously without this compounding?
- **Value pluralism:** Different humans have different values. Whose preferences does the reward model encode? RLAIF with a constitution makes this explicit but doesn't resolve whose constitution to use.
- **Constitutional AI at the capability frontier:** Does AI critique become more or less reliable as the model being critiqued becomes more capable than the critic?

---

## Key Sources

- Ouyang et al. 2022 — "Training language models to follow instructions with human feedback" (InstructGPT)
- Bai et al. 2022 — "Constitutional AI: Harmlessness from AI Feedback" (Anthropic)
- Rafailov et al. 2023 — "Direct Preference Optimization: Your Language Model is Secretly a Reward Model"
- Gao et al. 2022 — "Scaling Laws for Reward Model Overoptimization"
- DeepSeek-AI 2025 — "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning"
- Anthropic 2023 — "Model Card and Evaluations for Claude Models"
- Ziegler et al. 2019 — "Fine-Tuning Language Models from Human Preferences" (early RLHF)