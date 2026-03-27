---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: pac-bayes-generalization-bounds.md, implicit-regularization-sgd-flat-minima.md, grokking-delayed-generalization.md, ../information-theory/double-descent-benign-overfitting.md
---

# Neural Tangent Kernel and the Infinite-Width Limit

The **neural tangent kernel (NTK)** framework, introduced by Jacot, Gabriel & Hongler (2018), provides a theoretical account of how neural networks train in the limit of infinite width. It reframes neural network training as **kernel regression**, enabling rigorous analysis — but at the cost of operating in a regime (infinite width) that differs importantly from the finite-width networks used in practice.

---

## Background: Why Kernel Theory for Neural Networks?

### The Challenge of Nonlinear Dynamics

Training a neural network involves minimizing a highly nonlinear, non-convex loss function. Classical optimization theory provides limited guarantees for such settings. In contrast:
- **Linear models** trained with gradient descent have well-understood dynamics
- **Kernel methods** (SVMs, kernel ridge regression) have clean theory — generalization, convergence, and statistical properties are well-characterized

The NTK insight: **in the limit of infinite width, neural network training reduces to kernel regression**. This makes neural networks asymptotically tractable from a theoretical perspective.

---

## The Neural Tangent Kernel

### Kernel Definition

For a network $f(\theta, x)$ with parameters $\theta \in \mathbb{R}^p$ and input $x \in \mathbb{R}^d$, the **neural tangent kernel** at initialization is:

$$K(x, x') = \left\langle \frac{\partial f(\theta, x)}{\partial \theta}, \frac{\partial f(\theta, x')}{\partial \theta} \right\rangle_{\theta \sim \text{init}}$$

where the inner product is over the parameter gradient vectors. $K(x, x')$ measures how similarly the network's output at $x$ and $x'$ respond to perturbations of the parameters.

**Interpretation**: Two inputs $x, x'$ have high $K(x, x')$ if moving $\theta$ to improve prediction at $x$ also improves it at $x'$ — they are "functionally correlated" through the network's gradient structure.

### The Key Theorem (Jacot et al. 2018)

**Theorem**: For a fully connected network with $L$ layers, as width $n \to \infty$ (all layers wide simultaneously), and with appropriate (NTK) parameterization:

1. At initialization: $K(x, x') = K_{\text{NTK}}(x, x')$ converges in probability to a *deterministic* kernel $K_{\text{NTK}}$.
2. **During training**: $K(x, x')$ remains approximately constant — it barely changes as gradient descent updates $\theta$.
3. **Training dynamics**: The network's output function $f(\cdot, \theta_t)$ evolves according to **linear dynamics** governed by $K_{\text{NTK}}$.

Consequence of (3): In the infinite-width limit, gradient descent on a neural network is equivalent to **kernel gradient descent** on the RKHS (Reproducing Kernel Hilbert Space) defined by $K_{\text{NTK}}$.

### Prediction at Convergence

For a regression problem with targets $y$, training data $X$, and kernel matrix $K_{XX} = [K_{\text{NTK}}(x_i, x_j)]$, the network's predictions at test input $x^*$ converge to:

$$\hat{y}(x^*) = K_{\text{NTK}}(x^*, X) K_{XX}^{-1} y$$

This is exactly the **kernel ridge regression predictor** with $\lambda \to 0$ (interpolation).

---

## The NTK Parameterization

### Standard vs. NTK Parameterization

The result requires a specific parameterization. In the standard parameterization:
$$f(x) = \frac{1}{\sqrt{n}} W_L \sigma\!\left(\frac{1}{\sqrt{n}} W_{L-1} \cdots \sigma\!\left(\frac{1}{\sqrt{n}} W_1 x\right)\right)$$

where each weight matrix $W_l \in \mathbb{R}^{n \times n}$ has entries drawn from $\mathcal{N}(0, 1)$. The $1/\sqrt{n}$ factors ensure variance stability (each pre-activation has finite variance as $n \to \infty$).

In the NTK regime, **learning rates must scale as $1/n$**: $\eta_{\text{NTK}} = \eta_0 / n$. This keeps parameter updates small relative to initialization, ensuring the kernel stays constant.

### The μP (Maximal Update) Parameterization

Greg Yang and colleagues (Yang & Hu 2021, the "Tensor Programs" series) showed that the standard NTK parameterization corresponds to a **lazy training regime** that does not feature learn effectively at any width. An alternative parameterization — **μP or maximal update parameterization** — allows features (representations in hidden layers) to change meaningfully at finite width, enabling **feature learning**.

The key distinction:
| Parameterization | Regime | Feature Learning |
|-----------------|--------|-----------------|
| NTK (standard + appropriate scaling) | Kernel regime, lazy training | No — network effectively linear |
| μP | Feature learning regime | Yes — hidden representations change |

μP's practical importance: under μP, **optimal hyperparameters (including learning rate) transfer from small to large models** — you can tune LR on a small model and apply it to a large one. This is directly relevant to training large-scale models efficiently.

---

## Predictions and Experimental Tests

### What the NTK Gets Right

1. **Convergence**: Gradient descent on wide networks converges to global minima (for sufficiently wide, appropriate loss functions and data). The NTK provides conditions under which this holds.
2. **Generalization in the overparameterized regime**: As an interpolating kernel method, NTK-based predictors achieve good generalization through the kernel's regularization properties — consistent with the benign overfitting literature.
3. **Structured predictions**: NTK predictions capture certain smooth inductive biases (e.g., preference for low-frequency functions in shallow networks — the "spectral bias" / frequency principle).

### Where the NTK Fails

**Empirically**, finite-width practical networks deviate substantially from NTK predictions:

1. **Feature learning**: In practice, intermediate representations (features) change substantially during training — they are not frozen at their random initialization values. NTK predicts features should barely change.
2. **Transfer learning**: Pre-trained features transfer because they encode meaningful representations. NTK features are random and do not transfer.
3. **Grokking** (`grokking-delayed-generalization.md`): NTK predicts monotone improvement; grokking shows delayed generalization after apparent convergence.
4. **Emergent capabilities at scale**: The NTK is width-independent (the limit kernel $K_{\text{NTK}}$ does not depend on training data statistics beyond input distribution). Emergent capabilities at large scale cannot be explained by a fixed kernel.
5. **Effect of architecture**: Specific architectural choices (residual connections, attention mechanisms, normalization) matter empirically but are smoothed away in the infinite-width limit.

**Conclusion**: The NTK is a valid description of a limiting regime, but practical networks at finite width are not in that regime — they feature learn, and their generalization cannot be fully captured by the NTK framework.

---

## The Kernel Regime vs. Feature Learning Regime

The distinction between regimes:

| Property | Kernel regime (NTK) | Feature learning regime (μP) |
|----------|---------------------|------------------------------|
| Hidden representations | Fixed at initialization | Update significantly during training |
| Effective model | Kernel machine with $K_{\text{NTK}}$ | Adaptive function approximator |
| Width dependence | Converges to deterministic kernel | Behavior changes with width |
| Benefit of depth | Captured by kernel depth | Additional computational expressivity |
| Applicability | Theoretical analysis, very wide lazy networks | Practical deep learning |

The challenge: **theory is much cleaner in the kernel regime, but practice uses the feature learning regime**. Closing this gap is one of the major open problems in deep learning theory.

---

## The NTK as a Partially Validated Framework

**Status in 2026**: The NTK framework is:

- **Valid as a theoretical tool**: It provides rigorous certificates for convergence in specific settings and analysis of training dynamics for wide shallow networks.
- **Useful for understanding **inductive biases** through the kernel's structure (e.g., why shallow networks prefer smooth functions).
- **Limited as a practical model** of modern large-scale transformers or deep convolutional networks, which clearly feature learn.
- **Foundational for the μP literature**: The NTK framework's limitations drove the development of μP, which has significant practical import.

The NTK represents a canonical example of a theoretical framework that is illuminating about the mathematical structure of learning while underdetermining the empirical phenomenon it was designed to explain.

---

## Key Papers

- Jacot, A., Gabriel, F., & Hongler, C. (2018). Neural tangent kernel: Convergence and generalization in neural networks. *Advances in Neural Information Processing Systems*, 31.
- Lee, J., Xiao, L., Schoenholz, S. S., et al. (2019). Wide neural networks of any depth evolve as linear models under gradient descent. *Advances in NeurIPS*, 32.
- Yang, G., & Hu, E. J. (2021). Feature learning in infinite-width neural networks. *Proceedings of ICML*.
- Yang, G., et al. (2022). Tensor programs V: Tuning large neural networks via zero-shot hyperparameter transfer. *Advances in NeurIPS*, 35.
- Chizat, L., Oyallon, E., & Bach, F. (2019). On lazy training in differentiable programming. *Advances in NeurIPS*, 32.
