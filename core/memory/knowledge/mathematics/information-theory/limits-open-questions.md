---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: ../../philosophy/history/contemporary/synthesis-open-questions.md, double-descent-benign-overfitting.md, vc-dimension-fundamental-theorem.md
---

# Limits, Open Questions, and Unexplained Phenomena

## The Landscape of What We Don't Understand

Information theory and statistical learning theory have provided powerful frameworks, but many fundamental questions remain open. This file catalogs the most important limits of current theory and the phenomena that resist explanation.

## Fundamental Limits

### 1. The Generalization Gap Between Theory and Practice

**The problem:** The tightest rigorous generalization bounds for deep neural networks are still far above the actual generalization gap observed in practice.

| Bound type | Typical guarantee | Actual observation |
|-----------|-------------------|-------------------|
| VC-based | Vacuous (> 100% error) | ~1-5% generalization gap |
| PAC-Bayes (best) | ~10-30% error for ImageNet | ~2-3% actual gap |
| Norm-based | Meaningful but loose | 2-10× tighter than observed |

**Why it matters:** We can observe that deep learning works, but our theoretical tools can't explain *how well* it works. The gap suggests missing theoretical ingredients — unknown structure in the learned representations, optimization landscape, or data distributions.

**Current consensus:** PAC-Bayes bounds are improving (Lotfi et al., 2022), and compression-based approaches are narrowing the gap. But a complete explanation remains elusive.

### 2. The Limits of Compression as Explanation

**The problem:** The compression-generalization thesis says "models that compress generalize." But:

1. **Not all compression is good.** A model can compress by memorizing hash functions — deterministic, short-description, but useless for generalization. The thesis works only when "compression" means capturing *genuine regularities*, but how do we distinguish genuine from spurious regularities without external validation?

2. **Kolmogorov complexity is uncomputable.** The "true" description length is undecidable. All practical MDL uses approximate description lengths, and different approximations can give different model rankings.

3. **Description language dependence.** MDL is invariant to the description language up to an additive constant, but that constant can be significant for finite-data problems. The choice of "language" (model class, prior, coding scheme) matters in practice — the Bayesian justification via the "universal prior" doesn't resolve this for real problems.

### 3. The Limits of Information-Theoretic Analysis of Deep Learning

**MI estimation in high dimensions is very hard.** For deterministic networks (like ReLU nets), the mutual information $I(X; L_k)$ between input and a hidden layer is technically infinite (the mapping is invertible for most inputs). Practical estimates depend on:
- Binning/discretization (artifacts, as Saxe et al. showed)
- Adding noise (changes the quantity being measured)
- Variational bounds (MINE, etc. — high-dimensional estimates are noisy)

The information bottleneck intuition is compelling, but making it rigorous for real deep networks remains an unsolved problem.

## Open Questions in Scaling

### 4. Why Power Laws?

**The observation:** Neural scaling laws follow power laws across many orders of magnitude:

$$L(N) \propto N^{-\alpha}$$

**The question:** Why power laws? Not exponential, not logarithmic, but power laws with remarkably consistent exponents.

**Partial explanations:**
- **Manifold hypothesis + intrinsic dimensionality:** If the data lies on a $d$-dimensional manifold, learning should scale as $N^{-k/d}$ for some $k$, giving power-law behavior with exponents determined by the data's intrinsic dimension
- **Broken power laws from multiple regimes:** Different scaling exponents for different aspects (syntax, semantics, world knowledge) might combine to produce an effective power law
- **Statistical mechanics analogies:** Power laws arise at critical points in physical systems; perhaps deep learning operates near a critical transition in representation space

**None of these explanations are complete.** The scaling law exponents (~0.076 for model size, ~0.095 for data in language modeling) remain unexplained from first principles. We don't know why these specific values, why they're relatively constant across architectures, or whether they will continue to hold.

### 5. Will Scaling Continue?

**The empirical question:** Do neural scaling laws extend indefinitely, or do they eventually saturate?

**Arguments for saturation:**
- All real-world data distributions have finite entropy → the scaling law must flatten at the entropy rate
- The marginal benefit of additional data/parameters eventually hits diminishing returns from the distribution's irreducible noise
- Empirical evidence of saturation on specific benchmarks (though new capabilities may emerge on others)

**Arguments against near-term saturation:**
- Current models are far from the entropy rate of natural language (estimated $H \approx 0.7-1.2$ bits/character; current models achieve $\sim$2 bits/character)
- Task diversity means different tasks saturate at different scales
- Emergence of new capabilities at each scale suggests untapped room

**The honest answer:** We don't know when scaling will saturate for any given capability. Current theory doesn't predict the saturation point.

### 6. Are Emergent Abilities Real?

**The debate:** Do large language models exhibit genuine phase transitions in capabilities, or is "emergence" a measurement artifact?

**Wei et al. (2022):** Documented examples of capabilities appearing suddenly at specific scales (e.g., chain-of-thought reasoning, multi-step arithmetic).

**Schaeffer et al. (2023):** Argued that many reported emergent abilities are artifacts of:
- Non-linear metrics (e.g., exact-match accuracy) applied to gradually improving capabilities
- Under-sampling of intermediate scales
- Selection bias in which capabilities are reported

**Current state:** The empirical phenomenon is real (certain benchmark scores improve sharply at certain scales), but its theoretical status is unclear. Whether this represents genuine computational phase transitions or metric artifacts remains actively debated. This matters for safety: if capability jumps are real, they're harder to predict and prepare for.

## Open Questions in Learning Theory

### 7. Distribution Shift and Robustness

**The gap:** Most learning theory assumes i.i.d. training and test data. In practice, distribution shift is ubiquitous:
- **Temporal shift:** The world changes (data drift)
- **Deployment shift:** The test distribution differs from training
- **Adversarial shift:** An adversary constructs worst-case inputs

Information theory provides some tools (KL divergence between train and test distributions bounds the generalization gap), but:
- KL divergence between high-dimensional distributions is hard to estimate
- The bound is often vacuous
- It doesn't prescribe what to do about the shift (only quantifies its impact)

**Robust generalization** — guarantees that work under distribution shift — is largely an unsolved problem, with active progress in domain adaptation, distributional robustness, and causal inference.

### 8. In-Context Learning

**The phenomenon:** LLMs can learn new tasks from a few examples provided **in the prompt**, without weight updates.

**The puzzle:** This is not covered by standard learning theory:
- Classical PAC bounds apply to weight updates; in-context learning doesn't modify weights
- The "hypothesis class" is defined by what the model can express as a function of the prompt
- The "sample complexity" depends on both the task difficulty and the model's prior knowledge

**Nascent theoretical frameworks:**
- **In-context learning as gradient descent:** Transformer attention implements an approximation of gradient descent in function space (von Oswald et al., 2023; Ahn et al., 2023)
- **In-context learning as Bayesian inference:** The model maintains an implicit posterior over task types and updates it given prompt examples (Xie et al., 2022)
- **In-context learning as function composition:** The model recognizes the task from examples and routes to an appropriate internal subroutine

No complete theory exists. In-context learning is arguably the most important unexplained capability of modern LLMs.

### 9. The Unreasonable Effectiveness of Scale

**The question:** Why do larger language models become better at tasks they were never explicitly trained on (reasoning, translation, code generation, etc.)? Cross-entropy loss on next-token prediction seems too simple to explain emergent general capabilities.

**Partial explanations:**
- **Solomonoff induction:** Next-token prediction is equivalent to learning a universal predictive distribution. As the model approaches optimal prediction, it must model all computable structure in the data — including structure that supports reasoning, translation, etc.
- **Compression implies understanding:** To predict the next token optimally, the model must build a world model. Reasoning, translation, and code generation are aspects of this world model being queried.
- **Task diversity in pre-training data:** The training data contains examples of reasoning, translation, code, etc. The model doesn't learn these from scratch — it learns to recognize and reproduce them from the data.

**What's missing:** We don't have a theory that predicts *which* capabilities emerge at *which scale*, or why cross-entropy loss is sufficient to elicit them. The connection from compression to capability is intuitive but not formally characterized.

### 10. Better Complexity Measures for Deep Learning

**The quest:** Find a complexity measure that:
- Is finite for overparameterized networks (unlike VC dimension)
- Explains actual generalization behavior (unlike norm-based bounds, which are often too loose)
- Can be computed or estimated efficiently
- Is stable across architectures and tasks

**Candidates under active research:**
- **Effective rank / intrinsic dimensionality:** How many degrees of freedom the model actually uses
- **Flatness of minima:** Sharper minima → higher complexity → worse generalization (Keskar et al., 2017). But flatness is definition-dependent (Dinh et al., 2017)
- **Local Rademacher complexity:** Adapts to the specific function learned, not the class
- **Compression factor:** Ratio of model size to compressed model size that maintains performance
- **Distillability:** How small a student model can replicate the teacher's behavior

None of these is fully satisfactory. A "correct" complexity measure for deep learning — one that tightly predicts generalization — remains the field's central open problem in theory.

## Philosophical Limits

### 11. Is Understanding Compression?

The compression-generalization thesis can be pushed further: **does compressing (predicting) language require "understanding" it?**

**Arguments for (compression requires understanding):**
- Optimal prediction requires modeling causal structure, logical relationships, and factual knowledge
- A sufficiently good compressor must represent the data-generating process, which for language involves human cognition and the external world
- Solomonoff induction: the optimal compressor is the optimal predictor, which is the optimal model of reality

**Arguments against:**
- Compression can exploit surface statistics without deep understanding (n-gram models compress well without "understanding" anything)
- There may be shortcuts: correlations that predict well without modeling underlying causes
- "Understanding" is ill-defined; attributing it to compressors may be an anthropomorphization

**The honest position:** Current language models compress language extraordinarily well and exhibit many behaviors associated with understanding (reasoning, explanation, creative composition). Whether they "understand" depends on what we mean by the word — which is a philosophical question, not an information-theoretic one.

## Summary of Open Frontiers

| Question | Status | Key obstacle |
|----------|--------|--------------|
| Why do deep nets generalize so well? | Partially explained (PAC-Bayes, compression) | Bounds still loose by 5-10× |
| Why power-law scaling? | Empirical, limited theory | No first-principles derivation of exponents |
| Will scaling continue? | Unknown | Can't predict saturation points |
| Are emergent abilities real? | Debated | Entangled with metric choices |
| Distribution shift generalization | Open | Most bounds are vacuous |
| In-context learning theory | Nascent | Multiple competing frameworks, none complete |
| Why does next-token prediction suffice? | Partially explained (Solomonoff-style arguments) | Formal gap between compression and capability |
| Right complexity measure for NNs | Open | No candidate is both tight and practical |
| Is understanding compression? | Philosophical | Depends on definitions |

## Implications for the Engram System

### 1. Epistemic Humility in Knowledge Files

These open questions remind us: knowledge files should be written with epistemic humility. Even the best-understood connections (compression-generalization) have gaps. Knowledge files should distinguish between:
- **Established results** (Shannon's theorems, VC fundamental theorem)
- **Strong empirical patterns** (scaling laws, double descent)
- **Theoretical frameworks under debate** (IB for deep learning, emergent abilities)
- **Open questions** (this file)

### 2. The System's Own Limits

The Engram system faces its own versions of these open questions:
- **Distribution shift:** The user's interests change over time; knowledge written for past needs may not fit future queries
- **Scaling uncertainty:** Will adding more knowledge files continue to improve performance, or will retrieval degradation set in?
- **Emergence:** Will enough accumulated knowledge produce qualitatively new capabilities (cross-domain insights, spontaneous connection-making)?
- **Compression quality:** Are the current summarization standards the right compression level, or is there a better trade-off?

These are empirical questions for the system's evolution — to be answered through ongoing operation, not a priori theory.

### 3. Recording the Unknown

One function of a knowledge base is to record not just what is known but what **isn't** known. This file serves that purpose for information theory and statistical learning theory. Future research that resolves these questions should update or supersede this file.

## Key References

- Jiang, Y., et al. (2020). Fantastic generalization measures and where to find them. In *ICLR 2020*.
- Zhang, C., et al. (2021). Understanding deep learning (still) requires rethinking generalization. *Communications of the ACM*, 64(3), 107–115.
- Wei, J., et al. (2022). Emergent abilities of large language models. *TMLR*.
- Schaeffer, R., Miranda, B., & Koyejo, S. (2023). Are emergent abilities of large language models a mirage? In *NeurIPS 2023*.
- von Oswald, J., et al. (2023). Transformers learn in-context by gradient descent. In *ICML 2023*.
- Xie, S.M., Raghunathan, A., Liang, P., & Ma, T. (2022). An explanation of in-context learning as implicit Bayesian inference. In *ICLR 2022*.
- Dinh, L., Pascanu, R., Bengio, S., & Bengio, Y. (2017). Sharp minima can generalize for deep nets. In *ICML 2017*.
- Keskar, N.S., et al. (2017). On large-batch training for deep learning: generalization gap and sharp minima. In *ICLR 2017*.