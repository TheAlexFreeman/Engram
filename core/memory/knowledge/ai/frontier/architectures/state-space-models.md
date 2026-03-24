---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: State space models — Mamba, S4, SSM theory, hybrid architectures
trust: medium
type: knowledge
related: ../../../software-engineering/systems-architecture/concurrency-models-for-local-state.md, ../reasoning/reasoning-models.md, ../alignment/rlhf-reward-models.md
---

# State Space Models: Mamba, S4, and SSM Theory

## Lede

State space models (SSMs) represent the most architecturally significant attempt to escape transformer attention's $O(n^2)$ scaling. They connect to the scaling thread (SSMs offer $O(n)$ inference with linear-time training, a fundamentally different compute allocation than attention), the dynamical-systems thread (SSMs are explicitly dynamical systems — their mathematical formulation is a continuous or discrete recurrence, exactly the structure that the dynamical frame applies to), and the memory thread (SSMs implement a compressed recurrent state that is analogous to working memory in a way transformer KV caches are not). Understanding SSMs requires understanding where and why they outperform transformers, and equally where they reliably fail.

---

## The SSM Foundation: S4

**Structured State Spaces for Sequences (Gu et al. 2021 — S4):**

A state space model defines a sequence transformation using the continuous-time linear system:

$$\mathbf{h}'(t) = \mathbf{A}\mathbf{h}(t) + \mathbf{B}x(t)$$
$$y(t) = \mathbf{C}\mathbf{h}(t) + \mathbf{D}x(t)$$

where $\mathbf{h}(t) \in \mathbb{R}^N$ is the hidden state, $x(t)$ is the input, $y(t)$ is the output, and $\mathbf{A}, \mathbf{B}, \mathbf{C}, \mathbf{D}$ are learned matrices.

This is a classical linear dynamical system. The key insight of S4: the structure of $\mathbf{A}$ can be constrained to a specific form (HiPPO matrices that efficiently represent history through orthogonal polynomial projections) that makes the system computationally tractable.

**Three equivalent representations:**
1. **Continuous ODE:** The formulation above — useful for mathematical analysis
2. **Recurrent (discrete):** Discretized for sequence processing:
   $\mathbf{h}_k = \bar{\mathbf{A}}\mathbf{h}_{k-1} + \bar{\mathbf{B}}x_k$, $y_k = \mathbf{C}\mathbf{h}_k$
3. **Convolutional:** The output can be written as a convolution of the input with the kernel $\mathbf{K} = (\mathbf{C}\bar{\mathbf{B}}, \mathbf{C}\bar{\mathbf{A}}\bar{\mathbf{B}}, ..., \mathbf{C}\bar{\mathbf{A}}^{L-1}\bar{\mathbf{B}})$

**The key computational trick:** The convolutional form allows parallel computation during training (all outputs computed simultaneously using FFT-based convolution), while the recurrent form allows efficient $O(1)$-per-step inference. This is the fundamental advantage over attention, which cannot be parallelized during autoregressive inference (each token depends on all previous tokens' states, which must be generated sequentially).

---

## Mamba: Selective State Spaces

**Mamba (Gu and Dao 2023):** The core limitation of S4 is that $\mathbf{A}$, $\mathbf{B}$, $\mathbf{C}$ are time-invariant — the dynamics are the same for every input token. This limits selective attention: S4 processes every input with equal weighting regardless of its content.

**Mamba's innovation: input-dependent state transitions.** The state matrices are functions of the current input:

$$\mathbf{B}_k = \text{Linear}(x_k), \quad \mathbf{C}_k = \text{Linear}(x_k), \quad \Delta_k = \text{softplus}(\text{Linear}(x_k))$$

where $\Delta_k$ controls the discretization step size (how much time passes between tokens, influencing how strongly the input modifies the state).

**Effect of selectivity:**
- When $\Delta_k$ is large: the model attends strongly to the current input, potentially overwriting previous state
- When $\Delta_k$ is small: the input is largely ignored; the state evolves slowly (equivalent to "ignoring this token")

This mechanism allows Mamba to selectively integrate relevant inputs and filter irrelevant ones — without the explicit quadratic attention computation.

**Training trick:** The input-dependent parameters break the convolutional view (since the kernel changes with input). Mamba uses a hardware-aware algorithm (parallel selective scan) that computes the recurrence efficiently on GPU hardware without materializing the full state sequence.

---

## Where SSMs Beat Transformers

**Long sequence processing:** For sequences where transformers would require impractically large KV caches (audio waveforms, genomic sequences, long-form video, raw sensor streams), SSMs are dramatically more memory-efficient. A Mamba model processing a 1M-token sequence maintains only the fixed-size hidden state; a transformer would require a 1M-token KV cache.

**Inference throughput:** At autoregressive generation time, Mamba runs in $O(1)$ per step (just the recurrence update). Transformer inference is $O(n)$ per step (KV cache lookup for all $n$ previous tokens). For very long generations, Mamba is dramatically faster.

**Linear-attention tasks:** Tasks where the relevant information is spread smoothly across the sequence without sharp cross-sequence dependencies (e.g., "given this message, summarize it") are handled efficiently by SSMs.

---

## Where SSMs Lose to Transformers

**Retrieval tasks:** The canonical weakness. Tasks requiring precise retrieval of specific information from context (e.g., "What was the value of X mentioned 10,000 tokens ago?") are hard for SSMs because:
- The fixed-size state must compress all of the prior context
- Specific earlier content may be compressed into or overwritten by later content
- Transformers can directly attend to arbitrary past positions with full fidelity

**In-context learning:** ICL requires the model to adapt its behavior based on a few examples — effectively doing fast within-context learning. Transformers, with their ability to attend to specific examples, handle this well. SSMs must learn from examples by integrating them into state, which loses the direct example retrieval.

**Associative recall (needle-in-haystack):** In the MQAR (Multi-Query Associative Recall) benchmark, transformers substantially outperform Mamba — this is exactly the "find this specific thing mentioned earlier" failure mode.

**Copying exact content:** Transformers can copy arbitrary substrings from context by direct attention. SSMs that have compressed content into state cannot always recover exact copies of specific earlier tokens.

---

## Hybrid Architectures: Jamba, Zamba, Falcon Mamba

**The insight:** SSMs are efficient for content aggregation and long-range integration; transformers are better for precise retrieval and in-context learning. Combining them can capture both advantages.

**Jamba (AI21 Labs 2024):** Alternates between Mamba and regular transformer attention layers at a 7:1 ratio (7 Mamba layers per attention layer). The attention layers provide precise retrieval capability; the Mamba layers handle efficient long-range integration. Results: comparable quality to pure-transformer models at significantly lower KV cache memory and better throughput.

**Zamba (Zyphra 2024):** Uses a shared attention block after every 6 Mamba blocks. The shared attention processes the full sequence for tasks that need retrieval; Mamba handles efficient summarization between attention calls.

**The architectural design question:** How many attention heads are needed, and where should they be placed, to recover the retrieval capability lost by SSMs? Current answers are empirical; theory is sparse.

---

## SSMs and the Dynamical Systems Frame

SSMs are explicitly dynamical systems in a way that transformers are only loosely. The Mamba recurrence:

$$\mathbf{h}_k = e^{\Delta_k \mathbf{A}} \mathbf{h}_{k-1} + \Delta_k e^{\Delta_k \mathbf{A}} \mathbf{B}_k x_k$$

is a time-varying linear dynamical system. The state $\mathbf{h}$ is a compressed representation of all past inputs; its evolution is governed by the system matrix $\mathbf{A}$ and modulated by the input-dependent terms.

**The state as lossy memory:** Unlike the transformer KV cache (which stores all past information exactly), the SSM state is a lossy compression of the past. What is retained is determined by the learned $\mathbf{A}$ matrix — the system "forgets" what the dynamics say to forget and "remembers" what the dynamics say to retain. This is learned forgetting, analogous to the LSTM gating mechanism but derived from continuous dynamical system theory.

**Phase portrait of the state:** The state $\mathbf{h}$ lives in $\mathbb{R}^N$ and evolves according to the matrix exponential $e^{\Delta \mathbf{A}}$. The stability and trajectory of the state space evolution is determined by the eigenvalues of $\mathbf{A}$. Negative real eigenvalues → convergent dynamics (state forgets quickly); imaginary eigenvalues → oscillatory dynamics (state encodes periodic patterns); the HiPPO initialization ensures the state covers multiple timescales simultaneously.

---

## Open Questions

- **The retrieval gap:** Can SSMs be made to handle retrieval-heavy tasks without adding attention layers? Theoretical lower bounds suggest information-theoretic limits on what fixed-size state can represent — the gap may be fundamental.
- **Scaling behavior:** The SSM scaling laws differ from transformer scaling laws. Are the optimal hyperparameters (state size, selectivity dimension) the same at all scales?
- **Hardware-architecture co-design:** Mamba's performance depends on specific GPU memory access patterns. As hardware evolves (potentially toward in-memory computing), the relative advantage of SSMs may change.
- **Theoretical understanding of selective scanning:** The parallel selective scan in Mamba is a clever engineering solution. Is there a cleaner mathematical formulation that would allow better theoretical analysis?

---

## Key Sources

- Gu et al. 2021 — "Efficiently Modeling Long Sequences with Structured State Spaces" (S4)
- Gu and Dao 2023 — "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"
- Dao and Gu 2024 — "Transformers are SSMs: Generalized Models and Efficient Methods with Structured State Space Duality" (Mamba-2)
- Lieber et al. 2024 — "Jamba: A Hybrid Transformer-Mamba Language Model" (AI21 Labs)
- Tiezzi et al. 2024 — "State Space Models as Foundation Models: A Control Theoretic Overview"
- Arora et al. 2024 — "Simple linear attention language models balance the recall-throughput tradeoff"
- Poli et al. 2023 — "Hyena Hierarchy: Towards Larger Convolutional Language Models"