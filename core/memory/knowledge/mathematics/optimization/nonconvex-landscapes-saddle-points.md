---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Non-Convex Landscapes and Saddle Points

## Core Idea

Deep learning optimisation is fundamentally non-convex: neural network loss functions have exponentially many critical points, and the loss surface is a high-dimensional landscape shaped by overparameterisation, data geometry, and architecture. The classical worry — getting trapped in bad local minima — turns out to be largely unfounded for overparameterised networks, where saddle points dominate, local minima are nearly global, and mode connectivity reveals a surprisingly benign geometry. Understanding this landscape is one of the central open problems at the intersection of optimisation theory, statistical mechanics, and deep learning theory.

## The Landscape of Non-Convex Optimisation

For a general non-convex function $f : \mathbb{R}^n \to \mathbb{R}$, critical points $\nabla f(x) = 0$ are classified by the Hessian $H = \nabla^2 f(x)$:

- **Local minimum**: $H \succeq 0$ (all eigenvalues $\geq 0$)
- **Local maximum**: $H \preceq 0$ (all eigenvalues $\leq 0$)
- **Saddle point**: $H$ has both positive and negative eigenvalues
- **Degenerate critical point**: $H$ has zero eigenvalues

**Index** of a critical point = number of negative Hessian eigenvalues. A minimum has index 0; a saddle of index $k$ has $k$ descent directions.

## Saddle Points Dominate in High Dimensions

**Observation** (Dauphin et al. 2014, Bray-Dean 2007): In high-dimensional random landscapes (and empirically in neural networks), most critical points are saddle points, not local minima.

**Random matrix theory argument**: For a random function on $\mathbb{R}^n$ (e.g., drawn from a Gaussian random field), at a critical point the Hessian is approximately a random matrix from the GOE ensemble. The probability that all $n$ eigenvalues are positive is exponentially small in $n$:
$$\Pr[\text{all eigenvalues} > 0] \sim e^{-cn^2}$$

More precisely, the number of critical points at energy $E$ with index $k$ follows a distribution concentrated near $k \approx n/2$ for typical energies. Low-index critical points (near-minima) concentrate at low energies.

**Implications**: Saddle points, not local minima, are the primary obstacle for gradient-based optimisation. But saddle points are *unstable* — almost all saddle points can be escaped by adding noise.

## Saddle-Point Escape

**Strict saddle property**: A function satisfies the strict saddle property if every critical point either (a) has $\nabla f(x) \neq 0$ (not critical), (b) is a local minimum ($\nabla^2 f(x) \succeq 0$), or (c) has $\lambda_{\min}(\nabla^2 f(x)) < -\gamma$ for some $\gamma > 0$.

If $f$ satisfies the strict saddle property:
- **GD with random initialisation** (Lee et al. 2016): Converges to local minima almost surely (the set of initial points converging to saddles has measure zero)
- **Perturbed GD** (Jin et al. 2017): Finds an $\varepsilon$-approximate local minimum in $O(1/\varepsilon^2)$ iterations with periodic noise injection
- **SGD**: The inherent noise in stochastic gradients suffices to escape saddle points efficiently

## Overparameterised Neural Networks

Modern neural networks are **overparameterised**: the number of parameters far exceeds the number of training samples. This regime has qualitatively different optimisation properties.

### Loss Surface Characteristics

**No bad local minima** (approximate results):
- **Linear networks** (Bhojanapalli et al. 2016, Kawaguchi 2016): Every local minimum of a linear network's loss is a global minimum.
- **Wide networks** (NTK regime): Sufficiently wide networks have loss surfaces that are approximately convex near initialisation (Du et al. 2019, Allen-Zhu et al. 2019). Gradient descent converges to a global minimum at a linear rate.
- **Empirical observation**: In practice, different random initialisations converge to solutions with similar training loss (near zero) but potentially different test performance.

### The Neural Tangent Kernel (NTK) Regime

For a network $f(x; \theta)$ with parameters $\theta \in \mathbb{R}^p$ (width $\to \infty$):
$$f(x; \theta) \approx f(x; \theta_0) + \nabla_\theta f(x; \theta_0)^\top (\theta - \theta_0)$$

The optimisation becomes a *kernel regression* problem with kernel $K(x, x') = \nabla_\theta f(x; \theta_0)^\top \nabla_\theta f(x'; \theta_0)$ — the NTK. In this regime:
- The loss landscape is effectively convex
- GD converges exponentially
- But the model learns like a fixed kernel method — no feature learning

The *feature learning* regime (finite width, large learning rate) is where the interesting deep learning phenomena occur, and is much less well understood.

## Mode Connectivity

**Observation** (Draxler et al. 2018, Garipov et al. 2018): Local minima found by SGD from different random initialisations are connected by paths of near-constant loss.

**Linear mode connectivity** (Frankle et al. 2020): For networks trained with the same data but different random seeds, the linear interpolation $\theta_\alpha = (1-\alpha)\theta_A + \alpha\theta_B$ often has low loss for all $\alpha \in [0, 1]$ — there is no loss barrier between solutions.

**Permutation symmetry**: Neural networks have discrete symmetries — permuting neurons within a layer doesn't change the function. Ainsworth et al. (2023) showed that after accounting for permutation symmetry, mode connectivity becomes near-universal.

**Loss landscape geometry**: These findings suggest that the loss surface, modulo symmetries, has a single connected basin — a much more benign picture than the "rugged landscape" intuition.

## Double Descent and Interpolation

**Classical bias-variance tradeoff**: Increasing model complexity eventually increases test error (overfitting).

**Double descent** (Belkin et al. 2019, Nakkiran et al. 2021): Test error follows a *double descent* curve:
1. **Under-parameterised regime** ($p < n$): Classical U-shaped curve
2. **Interpolation threshold** ($p \approx n$): Test error peaks sharply
3. **Over-parameterised regime** ($p \gg n$): Test error *decreases* again

The interpolation threshold corresponds to the point where the model barely fits the training data — small perturbations cause large parameter changes. In the overparameterised regime, many interpolating solutions exist, and SGD finds ones with good generalisation properties (implicit bias toward low-complexity solutions).

**Connection to statistical mechanics**: The double descent phenomenon has been rigorously analysed using random matrix theory and statistical mechanics tools — see [../statistical-mechanics/statistical-mechanics-of-learning.md](../statistical-mechanics/statistical-mechanics-of-learning.md).

## The Edge of Stability

**Cohen et al. (2021)**: When training neural networks with gradient descent at a fixed learning rate $\eta$, the largest eigenvalue of the Hessian $\lambda_{\max}(\nabla^2 f)$ initially grows, then stabilises near $2/\eta$ — the "edge of stability."

At this edge:
- The loss is non-monotone (oscillates) but still decreases on average
- Standard convergence theory (which requires $\eta < 2/L$) doesn't apply
- The dynamics self-organise to the boundary of stability

This is a *self-organised criticality* phenomenon in optimisation — connecting to [dynamical systems](../dynamical-systems/self-organized-criticality.md).

## Sharpness and Generalisation

**Flat minima hypothesis** (Hochreiter-Schmidhuber 1997): Flat minima (low Hessian eigenvalues) generalise better than sharp minima.

**PAC-Bayes bounds**: For a posterior distribution $Q$ centred at parameters $\theta$:
$$\text{Generalisation gap} \leq O\left(\sqrt{\frac{\text{KL}(Q \| P)}{n}}\right)$$

Flat minima correspond to posteriors $Q$ with large variance, giving small KL divergence to a prior $P$ — hence better bounds.

**Sharpness-Aware Minimisation (SAM)** (Foret et al. 2021): Explicitly minimises:
$$\max_{\|\epsilon\| \leq \rho} f(\theta + \epsilon)$$

This seeks parameters that have low loss in a neighbourhood — a direct operationalisation of flatness. SAM consistently improves generalisation across architectures.

## Connections

- **Convex analysis**: Non-convexity breaks the guarantees of classical convex optimisation — see [convex-analysis-separation](convex-analysis-separation.md)
- **Gradient descent**: Convergence theory in the convex case vs the non-convex reality — see [gradient-descent-convergence](gradient-descent-convergence.md)
- **Duality**: GANs have non-convex-non-concave minimax structure — see [duality-theory-minimax](duality-theory-minimax.md)
- **Spin glasses**: Loss landscapes have spin-glass-like structure — see [../statistical-mechanics/spin-glasses-replica-method.md](../statistical-mechanics/spin-glasses-replica-method.md)
- **Hopfield-Boltzmann**: Energy landscapes in associative memory — see [../statistical-mechanics/hopfield-boltzmann-machines.md](../statistical-mechanics/hopfield-boltzmann-machines.md)
