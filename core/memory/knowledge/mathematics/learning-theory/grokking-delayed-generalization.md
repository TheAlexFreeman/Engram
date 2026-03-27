---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: pac-bayes-generalization-bounds.md, implicit-regularization-sgd-flat-minima.md, neural-tangent-kernel-infinite-width.md, ../information-theory/double-descent-benign-overfitting.md
---

# Grokking: Delayed Generalization in Neural Networks

**Grokking** (Power et al. 2022) is a striking training phenomenon in which a neural network achieves near-perfect training performance long before it generalizes — then, unexpectedly, after thousands of additional training steps, generalization occurs rapidly and dramatically. The name comes from Robert Heinlein's *Stranger in a Strange Land* (to "grok" = to deeply understand).

Grokking demonstrates that training loss convergence does not imply generalization, and vice versa — the relationship between training dynamics and generalization is more complex than classical theory suggests.

---

## The Experiment: Algorithmic Tasks and Delayed Generalization

### Setup (Power et al. 2022)

Power et al. trained small transformer models on **modular arithmetic** tasks:
- Task: Predict $a \circ b \pmod{p}$ for various operations $\circ$ (addition, subtraction, multiplication, division)
- Variables: $a, b \in \{0, 1, \ldots, p-1\}$ for prime $p$
- Training/test split: ~50% of all $(a, b)$ pairs used for training; remainder held out
- Network: Small transformer (~2 layers, ~4 heads, embedding dimension ~128)
- Training: Adam optimizer, weight decay regularization

### The Grokking Pattern

| Training phase | Training loss | Test loss (generalization) |
|----------------|--------------|---------------------------|
| Early           | Rapidly drops to 0 | Remains near chance (~100% error) |
| Middle          | Stays at 0 | Still near chance |
| Late (grokking) | Stays at 0 | **Suddenly drops to near 0** |

The gap between training convergence and test convergence can be **hundreds of thousands of steps** — orders of magnitude longer than the initial training phase. In some experiments, models that had "memorized" training data for 50,000 steps suddenly generalized after 500,000 steps.

### Weight Decay as Grokking Trigger

Critical finding: **weight decay is necessary for grokking**. Without regularization:
- The network memorizes training data and stays stuck
- Generalization never occurs (on these tasks in these settings)

With appropriate weight decay, the dynamics eventually find a compressed, generalizing solution. This strongly suggests that grokking is a regularization story: the optimizer continues to balance training fit against weight magnitude, and eventually this pressure finds an algorithm rather than a lookup table.

---

## Mechanistic Explanations

Multiple non-exclusive mechanistic accounts have been proposed:

### 1. Representation Complexity Theory (Nanda et al. 2023)

Nanda et al. reverse-engineered the *exact circuit* learned by a 1-layer transformer for modular addition ($a + b \pmod{113}$). The network learned:

**A Fourier-space algorithm**: The model represents $a$ and $b$ as vectors of Fourier features for specific frequencies $\omega$. It computes attention patterns that implement the Fourier convolution $e^{i\omega a} \cdot e^{i\omega b} = e^{i\omega(a+b)}$, then applies an MLP to decode the $(a+b) \bmod p$ from the Fourier features.

**Before grokking**: The network uses a memorization circuit — essentially a lookup table in its embedding weights.
**After grokking**: The network has discovered the Fourier algorithm — a compact, structured representation that *generalizes* to unseen combinations.

**The transition**: During grokking, memorization and generalization circuits coexist; under weight decay pressure, the memorization circuit (which requires larger weight magnitudes) is suppressed, and the generalizing circuit (more efficient) dominates.

### 2. Weight Norm Regularization Story

Building on representation complexity: the grokking transition corresponds to a specific pattern in the **weight norm**:

1. **Phase 1** (memorization): Weights grow — the network stores training data in large, specific weight configurations.
2. **Transition** (grokking): Weight norm suddenly decreases — regularization pressure finds a more compact solution.
3. **Phase 2** (generalization): Weights stabilize at lower magnitude — the network has found a compressed algorithm.

Evidence: tracking L2 norm of embedding weights during training shows a sharp drop correlated with the grokking transition in test accuracy.

### 3. Phase Transition Framing

Grokking can be interpreted as a **first-order phase transition** in a statistical physics sense:
- The loss landscape has two basins: a memorization solution and a generalization solution
- These basins are separated by an energy barrier
- With regularization, the generalization basin becomes thermodynamically preferred, but the system remains in the memorization basin (metastable state) until fluctuations enable a transition
- The transition appears discontinuous and sudden — characteristic of first-order transitions

This framing connects grokking to the **double descent** literature (`../information-theory/double-descent-benign-overfitting.md`) and to **sharpness transitions** in training (the generalization basin is flatter → lower SAM energy).

### 4. Algorithmic Efficiency / Occam's Razor

From an MDL perspective: the generalizing solution is more compressible (uses less description length) than the memorizing solution. Regularization acts as a push toward minimum description length solutions. Grokking occurs when the optimizer, following this pressure long enough, finds the shorter description — the algorithm rather than the lookup table.

---

## Grokking as a General Phenomenon

### Beyond Modular Arithmetic

Subsequent work found grokking in:
- **Simple neural network architectures** on parity and sparse parity tasks (Barak et al. 2022)
- **Language models** on certain structured reasoning tasks
- **In-context learning**: forms of delayed generalization where a model performs poorly on in-context examples for many training steps before suddenly acquiring in-context learning ability
- **Arithmetic in larger language models**: Grokking-like dynamics observed in transformer models trained on arithmetic tasks at larger scale

### Grokking on Different Scales

Power et al.'s original result used small models and algorithmic tasks. Whether grokking explains general dynamics of large-scale language model training is an open question. The training dynamics of GPT-scale models are much harder to analyze mechanistically.

---

## Connections to Other Learning Theory Phenomena

| Phenomenon | Connection to Grokking |
|-----------|----------------------|
| Double descent | Both involve non-monotone generalization trajectories; grokking = temporal double descent |
| SAM / flat minima | Generalization basin is flatter; SAM-like dynamics may accelerate grokking |
| PAC-Bayes bounds | Late grokking circuit has lower KL divergence from Gaussian prior → tighter bound |
| NTK | NTK predicts monotone generalization dynamics — grokking falsifies NTK description for these tasks |
| Implicit regularization | Grokking is implicit regularization finding a more efficient solution after memorization |

---

## Implications for Training Larger Models

Grokking suggests that:

1. **Training loss convergence is not a reliable stopping criterion** for generalization.
2. **Weight decay is a meaningful inductive bias** on which solution is eventually found.
3. **Algorithmic tasks may require long training** simply to find the compact, generalizing solution — early stopping could prevent this.
4. **Mechanistic interpretability** (circuit-level analysis) can reveal what generalization actually looks like — a nontrivial algorithm rather than interpolation.

For LLM training:
- Chain-of-thought reasoning may follow grokking dynamics (model first memorizes CoT patterns, then internationalizes the reasoning algorithm)
- Mathematical and code tasks may benefit from extended training beyond apparent training-loss convergence

---

## Open Questions

1. **Does grokking occur in large-scale pretraining?** Or is it confined to small-data algorithmic settings?
2. **Can grokking be accelerated?** Early experiments suggest SAM-related training, curriculum learning, and structured data augmentation all reduce the delay.
3. **Is the phase-transition framing predictive?** Statistical physics approaches could, in principle, predict the grokking time from properties of the loss landscape.
4. **Grokking without weight decay?** Alternative regularization (dropout, data augmentation) can trigger grokking, suggesting weight decay is one of several routes to the generalizing basin.

---

## Key Papers

- Power, A., Gururangan, S., Zhao, Y., Charton, F., & Lucas, J. (2022). Grokking: Generalization beyond overfitting on small algorithmic datasets. *ICLR 2022 PAIR Workshop*. arxiv:2201.02177.
- Nanda, N., Chan, L., Lieberum, T., Smith, J., & Steinhardt, J. (2023). Progress measures for grokking via mechanistic interpretability. *ICLR 2023*. arxiv:2301.05217.
- Barak, B., Edelman, B., Goel, S., Kakade, S., Malach, E., & Zhang, C. (2022). Hidden progress in deep learning: SGD learns parities near the computational limit. *NeurIPS 2022*.
- Liu, Z., Kitouni, O., Nolte, N., Michaud, E. J., Tegmark, M., & Williams, M. (2022). Towards understanding grokking: An effective theory of representation learning. *NeurIPS 2022*.
