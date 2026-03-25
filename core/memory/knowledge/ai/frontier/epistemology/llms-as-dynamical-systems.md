---
created: 2026-03-19
cross_references:
- knowledge/_unverified/philosophy/synthesis-intelligence-as-dynamical-regime.md
- knowledge/_unverified/philosophy/compression-intelligence-ait.md
- knowledge/_unverified/philosophy/free-energy-autopoiesis-cybernetics.md
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: LLMs as dynamical systems — activation trajectories, in-context learning, reasoning
  as trajectory extension
trust: medium
related: compression-and-intelligence.md, knowledge-and-knowing.md, ../../../../mathematics/dynamical-systems/dynamical-systems-fundamentals.md, ../../../../philosophy/synthesis-intelligence-as-dynamical-regime.md, ../../../../philosophy/phenomenology/synthesis-phenomenology-dynamical-systems.md
---
type: knowledge
---

# LLMs as Dynamical Systems

## Lede

The dynamical systems frame offers the most mechanistically coherent vocabulary for describing what happens inside a language model during inference. It connects directly to Alex's synthesis in `synthesis-intelligence-as-dynamical-regime.md` (intelligence as a dynamical regime navigating between rigidity and chaos) and `compression-intelligence-ait.md` (LLMs as learned compression functions). A transformer's forward pass is a deterministic flow through a high-dimensional activation space, with each layer applying a learned transformation. Different prompts initialize different starting conditions; different outputs correspond to different basins of attraction in the final layer's distribution over next tokens. Chain-of-thought reasoning, in-context learning, and even prompt sensitivity all have natural interpretations in this dynamical frame.

---

## The Forward Pass as a Trajectory

A transformer processes tokens by passing a residual stream through a series of layers. At each position $t$ (token index), the residual stream $\mathbf{x}_t^{(\ell)} \in \mathbb{R}^d$ evolves as:

$$\mathbf{x}_t^{(\ell+1)} = \mathbf{x}_t^{(\ell)} + \text{Attn}^{(\ell)}(\mathbf{X}^{(\ell)})_t + \text{MLP}^{(\ell)}(\mathbf{x}_t^{(\ell)} + \text{Attn}^{(\ell)}(\mathbf{X}^{(\ell)})_t)$$

This is a residual flow: each layer adds a correction to the previous state. The residual connection means that information from layer 0 (the embedding) can "flow through" to the output, with each layer selectively modifying the representation.

**Layer roles (empirically observed):**
- **Early layers (0–20%):** Feature extraction — syntactic structure, token type identification, local context processing
- **Middle layers (20–70%):** Semantic processing — entity disambiguation, relation extraction, world-knowledge lookup and integration
- **Late layers (70–100%):** Output formation — projecting to the vocabulary distribution, suppressing unlikely next tokens, applying stylistic adjustments

This layered structure resembles a dynamical system with different time-scales at different hierarchical levels — early layers process fast (local token) dynamics, late layers process slow (document-level) dynamics.

---

## The Context as Initial Condition

In the dynamical systems frame, the input context functions as an **initial condition** for the computation. The prompt text determines the embedding of each token, which determines the initial state of the residual stream at every position. The forward pass then evolves these initial conditions through 32–100+ layers, arriving at a final distribution over what comes next.

**Why prompt sensitivity is expected:** In nonlinear dynamical systems, small changes in initial conditions can lead to large divergence in trajectories (sensitivity to initial conditions is the Lorenz butterfly effect). LLMs exhibit this: small prompt changes can dramatically alter outputs. This is not random — specific prompt changes activate different computational pathways (circuits, in the mechanistic interpretability vocabulary) and thus different downstream distributions.

**Why this frame helps:** Thinking of the prompt as an initial condition shifts the question from "what did the model learn about X" to "what trajectory does the context initialized by X follow through the activation space, and where does it terminate?" This is more mechanistically precise and makes the role of context length natural: more context = more detailed initial condition = better-constrained trajectory.

---

## In-Context Learning as Transient Dynamics

In-context learning (ICL) — the ability of an LLM to learn a new task from a few examples in the prompt, without any weight update — is one of the most surprising capabilities to emerge from scale. The dynamical frame provides a natural vocabulary for it.

**The induction head mechanism** (Olsson et al. 2022; see also `interpretability/mechanistic-interpretability.md`) implements a specific circuit that, given examples of pattern [A] → [B] in the context, increases the probability of [B] following [A] in new positions. This is a transient dynamical computation: the context establishes a "regime" of behavior (the mapping [A] → [B]) that then governs subsequent token generation.

**ICL as implicit Bayesian inference (Xie et al. 2021):** There is a theoretical account under which ICL corresponds to Bayesian inference over a prior over tasks induced by the pretraining distribution. Each example in the prompt updates the model's implicit posterior over which task it is performing. This is mathematically consistent with the dynamical frame: each example shifts the effective initial condition of the residual stream, narrowing the trajectory toward the relevant task basin.

**Key feature:** ICL is a transient dynamical phenomenon — it exists only within the active context window. It does not persist across conversations, does not update weights, and cannot be "stored" without explicit memory mechanisms. This is the central limitation of pure in-context state: high expressiveness within the window, zero persistence outside it.

**Connection to cognitive science:** Human working memory operates similarly — it holds a dynamical context (activated schema, current task frame) that organizes perception and action, but must be explicitly consolidated to persist. The LLM's context window is an in-silico working memory with much larger capacity than biological WM but the same transience.

---

## Reasoning as Extended Trajectory

Chain-of-thought reasoning has a clean interpretation in the dynamical frame: it extends the computational depth available to the model by unrolling computation through the output space.

In a single forward pass to generate the final answer directly, the model has $L$ layers to process the input. When the model first generates intermediate reasoning tokens, those tokens become part of the context for subsequent forward passes. Each intermediate token is:
1. A commitment to a partial conclusion
2. A new input to the next forward pass, extending the effective depth

**Depth vs. width trade-off:** Transformers have a fixed number of layers (depth) and a fixed hidden dimension (width). For problems that require more computational steps than $L$ layers can represent, the only option is to use more forward passes — which chain-of-thought provides. The reasoning chain is computation unrolled into sequence space.

**Why CoT helps with multi-step problems:** Any problem whose optimal solution requires more than $O(L)$ "computational steps" (in an appropriately defined sense) cannot be solved in a single forward pass without residualization of intermediate state into explicit tokens. Multi-step math, code with complex logic, planning under constraints — these are all problems where solution depth exceeds pass depth.

**The attractor hypothesis:** If we model the residual stream at the final token position as a dynamical system being driven toward an output distribution, then difficult questions (many plausible answers) correspond to flat attractors (many directions have similar probability), while easy questions (clear answer) correspond to sharp attractors. Chain-of-thought exploration can be understood as steering the trajectory toward a sharper attractor by progressively eliminating competing possibilities through intermediate tokens.

This is speculative but consistent with the empirical observation that CoT helps most on problems with "many plausible but wrong paths" — geometry problems, code debugging, counterfactual reasoning.

---

## Activation Spaces and Feature Geometry

The linear representation hypothesis (underlying the SAE work in `interpretability/mechanistic-interpretability.md`) asserts that concepts are represented as directions in the residual stream's $\mathbb{R}^d$ space. This has a direct dynamical interpretation:

**Feature directions as stable subspaces:** If a concept C is represented as direction $\mathbf{v}_C$, then the set of activation states where C is "active" is an affine subspace. The network's computation can be understood as moving activations through these subspaces, combining them according to the logic of the task.

**Attention as dynamical coupling:** The attention mechanism at each layer computes weighted mixtures of token representations, creating interaction terms between all positions. In the dynamical metaphor, this is a form of instantaneous coupling — the trajectory of position $t$ is influenced by the trajectories of all other positions through the attention weights.

**Layerwise convergence:** Empirically, the residual stream representations tend to converge toward stable semantic representations in middle layers, then refine toward specific output predictions in late layers. This resembles a system approaching a fixed point before being read out — the middle-layer representations are "phase space mid-points" rather than transients.

---

## Dynamical Regime and the Edge of Chaos

The synthesis in `synthesis-intelligence-as-dynamical-regime.md` argues that intelligence corresponds to a dynamical regime balanced between order (rigidity, predictability) and chaos (flexibility, sensitivity). This applies to LLMs in a specific form:

**Temperature as a regime parameter:** Sampling temperature directly controls the stability of the output distribution. Temperature = 0 (greedy sampling) is maximally ordered — the system always takes the highest-probability action, converging to a fixed attractor. High temperature is maximally chaotic — outputs are random. Useful generation is at intermediate temperature, near the boundary between order and chaos.

**The beam search parallel:** MCTS-style reasoning search (used in o1-class models) explicitly explores multiple trajectory branches and selects by quality. This is the dynamical systems version of branch-and-bound optimization: the computation is not a single trajectory but an ensemble of trajectories sampled from the same initial condition, with selection operating at the ensemble level.

**Phase transitions in capability:** The emergence of capabilities at scale (in-context learning appearing above ~1B parameters, chain-of-thought above ~100B parameters) resembles phase transitions in physical systems — abrupt qualitative changes in the system's dynamical regime triggered by continuous changes in a control parameter (model size). The analogy is not just metaphorical: the mathematical structure of phase transitions in thermodynamics (symmetry breaking, order parameters) may apply to these capability transitions.

---

## Limits of the Dynamical Frame

The dynamical systems frame is illuminating but has limits for LLMs:

1. **Non-stationarity:** The "dynamical system" changes with each new token in the context (the system is recurrent in generation but not in the mathematical sense of a fixed equation of motion). The dynamics shift as context changes.

2. **Discreteness:** The output is a discrete probability distribution over tokens, not a continuous trajectory. The "attractor" is not a point in phase space but a distribution over a discrete vocabulary.

3. **No autonomous dynamics:** A physical dynamical system evolves autonomously. An LLM produces output only when queried; it has no autonomous evolution without input. (This is different from biological neural networks, which have ongoing dynamics even in the absence of input — the default mode network, etc.)

4. **Scale of the space:** The residual stream is $\mathbb{R}^d$ with $d$ ranging from 4096 to 12288 for frontier models. Geometric intuitions from low-dimensional dynamical systems may not transfer.

---

## Open Questions

- **Do attractor structures exist in the residual stream?** Can we identify stable fixed points corresponding to stable semantic representations using tools from dynamical systems analysis (Lyapunov exponents, bifurcation analysis)?
- **Is the edge-of-chaos hypothesis testable for LLMs?** Can we define an order parameter for LLM generation that shows a phase transition at optimal temperature?
- **What changes in activation geometry when the model is wrong vs. right?** Do incorrect high-confidence answers have different attractor basin structure than correct ones?
- **Does CoT extend depth monotonically?** Is more chain-of-thought always better, or does the trajectory at some point enter a chaotic regime (over-reasoning, self-contradicting)?

---

## Key Sources

- Olsson et al. 2022 — "In-context Learning and Induction Heads"
- Xie et al. 2021 — "An Explanation of In-context Learning as Implicit Bayesian Inference"
- Elhage et al. 2021 — "A Mathematical Framework for Transformer Circuits"
- Geva et al. 2021 — "Transformer Feed-Forward Layers Are Key-Value Memories"
- Nostalgebraist 2020 — "Interpreting GPT: The Logit Lens" (logit lens for layerwise activation analysis)
- Schuster et al. 2022 — "Confident Adaptive Language Modeling" (early exit as dynamical regime termination)
- Liu et al. 2023 — "Sophia: A Scalable Stochastic Second-order Optimizer for Language Model Pre-training" (loss landscape geometry)
- Cross-reference: `knowledge/_unverified/philosophy/synthesis-intelligence-as-dynamical-regime.md`
- Cross-reference: `knowledge/_unverified/philosophy/free-energy-autopoiesis-cybernetics.md`
