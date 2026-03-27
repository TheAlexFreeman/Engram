---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: ../information-theory/pac-learning-sample-complexity.md, ../information-theory/compression-generalization-connection.md, implicit-regularization-sgd-flat-minima.md, learning-theory-synthesis.md
---

# PAC-Bayes Generalization Bounds

PAC-Bayes bounds are a family of generalization bounds that survive the overparameterized regime where classical VC theory fails. By framing generalization as a statement about the entire *posterior distribution* over hypotheses rather than a single hypothesis, PAC-Bayes bounds remain non-vacuous for neural networks with more parameters than training examples.

**Prerequisite**: Classical PAC learning framework (see `../information-theory/pac-learning-sample-complexity.md`); the compression-generalization connection (see `../information-theory/compression-generalization-connection.md`), which introduces PAC-Bayes from the information-theoretic side.

---

## From PAC to PAC-Bayes

### The Gap Classical PAC Leaves

Classical PAC bounds control the generalization error of a *fixed* hypothesis $h$:

$$\mathbb{P}\left[\text{err}(h) \leq \hat{\text{err}}(h, S) + \sqrt{\frac{\ln|\mathcal{H}| + \ln(1/\delta)}{2m}}\right] \geq 1 - \delta$$

For infinite hypothesis classes, the bound uses the VC dimension $d$:

$$m(\varepsilon, \delta) = O\!\left(\frac{d + \ln(1/\delta)}{\varepsilon^2}\right)$$

In the **overparameterized regime** ($d \gg m$ for neural networks), VC-dimension bounds are vacuous — they predict generalization error could be arbitrarily large, yet networks generalize well. PAC-Bayes addresses this by replacing the choice of a single worst-case hypothesis with a probabilistic "vote" across hypotheses.

### The PAC-Bayes Setup

**Prior** $P$: A distribution over $\mathcal{H}$ fixed *before* seeing training data $S$.
**Posterior** $Q$: A data-dependent distribution over $\mathcal{H}$, chosen after seeing $S$.

The predictor is a **Gibbs classifier** that randomly samples $h \sim Q$ and predicts $h(x)$. Its generalization error is:

$$\text{err}(Q) = \mathbb{E}_{h \sim Q}[\text{err}(h)]$$

The empirical error is:

$$\hat{\text{err}}(Q, S) = \mathbb{E}_{h \sim Q}[\hat{\text{err}}(h, S)]$$

---

## McAllester's PAC-Bayes Theorem

### Statement

**Theorem** (McAllester 1999): For any prior $P$ over $\mathcal{H}$, for all posteriors $Q$ simultaneously, with probability $\geq 1 - \delta$ over the draw of $S \sim \mathcal{D}^m$:

$$\text{err}(Q) \leq \hat{\text{err}}(Q, S) + \sqrt{\frac{\text{KL}(Q \| P) + \ln(m/\delta)}{2(m-1)}}$$

where $\text{KL}(Q \| P) = \int_\mathcal{H} \ln\!\frac{dQ}{dP} \, dQ$ is the KL divergence from prior to posterior.

### Interpretation

The generalization gap is controlled by:
1. **The training error** $\hat{\text{err}}(Q, S)$ — the posterior's average performance on the training set.
2. **The posterior-prior complexity** $\text{KL}(Q \| P)$ — how much information the training data added over prior belief. If $Q = P$ (training data didn't change our beliefs), then $\text{KL}(Q \| P) = 0$ and the bound is tight around training error. If $Q$ is concentrated near a single point (max posterior), $\text{KL}(Q \| P) = \ln(1/P(h^*))$, recovering something like the ordinary PAC complexity.

**The crucial insight**: The bound is *tight* even when $|\mathcal{H}| = \infty$, as long as the posterior $Q$ remains close to the prior $P$ in KL divergence. Unlike VC bounds, PAC-Bayes does not require the hypothesis class to be small — it requires the learned distribution to not stray too far from what we believed a priori.

### The Role of the Prior

The prior $P$ must be chosen *before* seeing the data — this is the honesty constraint that gives the bound validity. A good prior should have:
- High probability on hypotheses that fit typical data well
- Smooth spread over hypothesis space (avoiding too-peaked priors that could be exploited)

**Gaussian prior over weights** is the natural choice for neural networks: $P = \mathcal{N}(0, \sigma^2 I)$ — i.i.d. Gaussian weights. The posterior $Q$ after training is some other distribution, and $\text{KL}(Q \| P)$ measures how far training moved us from the initial weight distribution.

---

## Key Extensions and Variants

### Catoni's Bound

Catoni (2007) derived a tighter bound that accounts for the convexity of the generalization gap function:

For $0 < C < 1$:

$$\text{err}(Q) \leq \frac{1}{1 - \frac{C}{2}} \left( \hat{\text{err}}(Q, S) + \frac{\text{KL}(Q \| P) + \ln(1/\delta)}{Cm} \right)$$

Catoni's bound is often tighter for small training error because it avoids the square-root and scales linearly with $m$ in the denominator.

### Data-Dependent Priors (Informed Priors)

**Ambroladze et al.** and others relaxed the requirement that the prior be independent of the training data by using a **held-out subset** to construct the prior:
- Split data $S = S_1 \cup S_2$
- Learn prior $P$ from $S_1$ (e.g., run a few gradient steps)
- Learn posterior $Q$ from $S_2$, with tightened bound

This "informed prior" approach dramatically tightens bounds in practice and is the basis for **PAC-Bayes compression certificates**.

### Excess Risk Decomposition

The generalization error of the posterior decomposes as:

$$\text{err}(Q) \leq \underbrace{\text{err}(h^*)}_{\text{approximation error}} + \underbrace{\hat{\text{err}}(Q, S) - \text{err}(h^*)}_{\text{estimation error}} + \underbrace{\text{generalization gap}}_{\text{bounded by PAC-Bayes}}$$

where $h^*$ is the optimal hypothesis in $\mathcal{H}$. PAC-Bayes controls only the last term; approximation error requires choosing a sufficiently rich hypothesis class.

---

## Why PAC-Bayes Survives the Overparameterized Regime

Classical VC bounds grow as $O(d/m)$ where $d$ is model dimension — catastrophic for large neural networks. PAC-Bayes bounds grow as $O(\text{KL}(Q \| P)/m)$, and empirical studies show that even very large neural networks exhibit:

- **Small KL divergence** relative to a Gaussian prior when measured in terms of weight perturbation: well-trained networks can be perturbed significantly without losing performance, suggesting the posterior is "broad" near the minimum — consistent with low KL.
- The connection to **flat minima** (see `implicit-regularization-sgd-flat-minima.md`): flat minima have high local entropy, corresponding to posteriors that don't stray far from a Gaussian prior — lower KL.

**Dziugaite & Roy (2017)** computed the first *non-vacuous* PAC-Bayes bound for a neural network on MNIST — demonstrating that PAC-Bayes bounds can be computed and are meaningful for real neural networks, unlike VC bounds.

---

## PAC-Bayes and Minimum Description Length

The PAC-Bayes bound connects to MDL (Minimum Description Length) via the coding interpretation of KL divergence:

$$\text{KL}(Q \| P) = \mathbb{E}_{h \sim Q}\left[\ln \frac{Q(h)}{P(h)}\right]$$

This is the expected extra coding cost of encoding samples from $Q$ using the code optimal for $P$. Low $\text{KL}$ means the learned distribution can be compactly described relative to the prior — consistent with the MDL principle that compression ↔ generalization.

The compression-generalization connection file (`../information-theory/compression-generalization-connection.md`) introduces this at the conceptual level; the PAC-Bayes bound is the formal version.

---

## Computable Generalization Certificates

A practical strength of PAC-Bayes is that the bound is **computable** without access to the true distribution $\mathcal{D}$:

1. Train a neural network to get posterior $Q$ (or approximate it as a Gaussian centered at the learned weights)
2. Measure $\hat{\text{err}}(Q, S)$ on training data
3. Compute $\text{KL}(Q \| P)$ analytically (closed form for Gaussian $Q$ and $P$)
4. Plug in to get an upper bound on test error

This is different from VC bounds, which require knowing $d$ (often not easily computable for complex architectures) and often overestimate dramatically.

**Limitation**: Current PAC-Bayes bounds, while non-vacuous, are still often loose — a network with 5% test error may have a PAC-Bayes bound of 15-20%. Active research aims to tighten bounds further.

---

## Connection to Flat Minima and Sharpness

PAC-Bayes theoretically justifies flat minima intuition (due to Hochreiter & Schmidhuber 1997):
- A **flat minimum** is a region of weight space where many nearby weights achieve low training error
- This corresponds to a **high-entropy posterior** around the minimum — many hypotheses are effective
- High-entropy posterior → small KL divergence from a diffuse prior → tighter PAC-Bayes bound
- Therefore, flat minima have provably better PAC-Bayes generalization guarantees than sharp minima for fixed training error

**SAM (Sharpness-Aware Minimization)** explicitly optimizes for this by seeking parameters that minimize the loss of a neighborhood (high local volume of good solutions) rather than just the loss at a point.

---

## Key Papers

- McAllester, D. A. (1999). Some PAC-Bayesian theorems. *Machine Learning*, 37(3), 355–363.
- Catoni, O. (2007). *PAC-Bayesian Supervised Classification: The Thermodynamics of Statistical Learning*. IMS.
- Dziugaite, G. K., & Roy, D. M. (2017). Computing nonvacuous generalization bounds for deep (stochastic) neural networks with many parameters. *Proceedings of UAI*.
- Alquier, P. (2024). User-friendly introduction to PAC-Bayes bounds. *Foundations and Trends in Machine Learning*, 17(2), 174–303.
- Langford, J., & Shawe-Taylor, J. (2002). PAC-Bayes & margins. *Advances in Neural Information Processing Systems*, 15.
