---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Duality Theory and Minimax Theorems

## Core Idea

Duality transforms a minimisation problem into a maximisation problem that provides bounds on — and often equals — the original optimum. The Lagrangian framework, strong duality conditions (Slater's), and the minimax theorem (von Neumann) share a common geometric core: the interchangeability of min and max under convexity. This structure appears in linear programming, game theory, mechanism design, information theory, and GANs — a deep unification across seemingly disparate fields.

## The Lagrangian Framework

Given the primal problem:
$$p^* = \min_x f_0(x) \quad \text{s.t.} \quad f_i(x) \leq 0, \; h_j(x) = 0$$

The **Lagrangian** is:
$$L(x, \lambda, \nu) = f_0(x) + \sum_{i=1}^m \lambda_i f_i(x) + \sum_{j=1}^p \nu_j h_j(x)$$

where $\lambda_i \geq 0$ are dual variables (multipliers) for inequality constraints and $\nu_j$ are dual variables for equality constraints.

**Lagrange dual function**:
$$g(\lambda, \nu) = \inf_x L(x, \lambda, \nu)$$

$g$ is always concave (as a pointwise infimum of affine functions of $(\lambda, \nu)$), regardless of whether the primal is convex.

**Dual problem**:
$$d^* = \max_{\lambda \geq 0, \nu} g(\lambda, \nu)$$

## Weak and Strong Duality

**Weak duality**: $d^* \leq p^*$ — always holds.

The **duality gap** is $p^* - d^*$.

**Strong duality**: $d^* = p^*$ — the gap closes. Holds under:

- **Slater's condition** (sufficient for convex problems): There exists a strictly feasible point $x_0$ with $f_i(x_0) < 0$ for all inequality constraints. This is very mild — it fails only when the feasible set is "degenerate."
- **LP duality**: Strong duality always holds for linear programs (no constraint qualification needed).
- **Refined conditions**: Mangasarian-Fromovitz, LICQ (linear independence constraint qualification), etc.

## KKT Conditions

If strong duality holds and the primal/dual optima are attained at $(x^*, \lambda^*, \nu^*)$, then the **Karush-Kuhn-Tucker** conditions hold:

1. **Stationarity**: $\nabla_x L(x^*, \lambda^*, \nu^*) = 0$, i.e., $\nabla f_0(x^*) + \sum_i \lambda_i^* \nabla f_i(x^*) + \sum_j \nu_j^* \nabla h_j(x^*) = 0$
2. **Primal feasibility**: $f_i(x^*) \leq 0$, $h_j(x^*) = 0$
3. **Dual feasibility**: $\lambda_i^* \geq 0$
4. **Complementary slackness**: $\lambda_i^* f_i(x^*) = 0$ for all $i$

For convex problems with Slater's condition, KKT conditions are both necessary and sufficient for optimality. They unify calculus-based optimality with geometric constraint analysis.

## LP Duality

The LP primal-dual pair:

| Primal | Dual |
|--------|------|
| $\min c^\top x$ | $\max b^\top y$ |
| $Ax \geq b$ | $A^\top y \leq c$ |
| $x \geq 0$ | $y \geq 0$ |

**Fundamental theorem of LP**: Exactly one of three cases holds:
1. Both primal and dual are feasible → both have optimal solutions with equal values
2. Primal unbounded → dual infeasible (and vice versa)
3. Both infeasible

**Complementary slackness**: $x_i^*(c_i - (A^\top y^*)_i) = 0$ and $y_j^*(A_j x^* - b_j) = 0$.

LP duality is the foundation for the simplex method's optimality certificate, sensitivity analysis, and the theory of total unimodularity.

## Von Neumann's Minimax Theorem

**Theorem** (von Neumann, 1928): For a two-player zero-sum game with payoff matrix $A$:

$$\max_{p \in \Delta_m} \min_{q \in \Delta_n} p^\top A q = \min_{q \in \Delta_n} \max_{p \in \Delta_m} p^\top A q$$

where $\Delta_k$ is the probability simplex. The *value* of the game exists, and optimal mixed strategies $(p^*, q^*)$ form a saddle point.

**Proof via LP duality**: The left side is an LP (maximise $v$ subject to $A^\top p \geq v \mathbf{1}$, $p \in \Delta_m$); the right side is its dual. Strong LP duality gives equality.

**Generalisation (Sion's minimax theorem)**: If $X, Y$ are convex compact sets and $f(x, y)$ is convex-concave (convex in $x$ for fixed $y$, concave in $y$ for fixed $x$):
$$\min_{x \in X} \max_{y \in Y} f(x, y) = \max_{y \in Y} \min_{x \in X} f(x, y)$$

## Saddle-Point Structure

A **saddle point** of $L(x, y)$ is a pair $(x^*, y^*)$ such that:
$$L(x^*, y) \leq L(x^*, y^*) \leq L(x, y^*), \quad \forall x, y$$

Saddle points are the intersection of two optimalities: $x^*$ minimises for fixed $y^*$, and $y^*$ maximises for fixed $x^*$.

**Primal-dual algorithms** compute saddle points iteratively:
- **Primal-dual gradient descent-ascent**: $x_{t+1} = x_t - \eta \nabla_x L$, $y_{t+1} = y_t + \eta \nabla_y L$
- Converges for convex-concave $L$ but can cycle or diverge for non-convex-non-concave problems
- **Extragradient method** (Korpelevich 1976) and **optimistic gradient** methods provide convergence guarantees even for bilinear problems

## Fenchel Duality and Conjugate Functions

The **Fenchel conjugate** (convex conjugate) of $f$:
$$f^*(y) = \sup_x \{y^\top x - f(x)\}$$

Properties:
- $f^*$ is always convex (even if $f$ is not)
- $f^{**} = f$ iff $f$ is convex and lower semicontinuous (Fenchel-Moreau theorem)
- Young's inequality: $f(x) + f^*(y) \geq x^\top y$, with equality iff $y \in \partial f(x)$

**Fenchel duality theorem**: For convex $f, g$ and linear $A$:
$$\min_x \{f(x) + g(Ax)\} = \max_y \{-f^*(-A^\top y) - g^*(y)\}$$

This provides an alternative route to strong duality that is often more natural for structured problems.

**Examples**:
- $f(x) = \frac{1}{2}\|x\|^2 \implies f^*(y) = \frac{1}{2}\|y\|^2$ (self-conjugate)
- $f(x) = \|x\|_1 \implies f^*(y) = \delta_{\|y\|_\infty \leq 1}$ ($\ell_1$ and $\ell_\infty$ norms are dual)
- $f(x) = e^x \implies f^*(y) = y \log y - y$ for $y > 0$ (exponential ↔ neg-entropy)

## Duality in Machine Learning and Information Theory

**Maximum entropy as a dual problem**: The MaxEnt distribution $\max_p H(p)$ subject to moment constraints is dual to the exponential family fitting problem $\min_\theta \log Z(\theta)$. This connects to [statistical mechanics](../statistical-mechanics/partition-function-free-energy.md).

**SVM duality**: The support vector machine primal (minimise $\|w\|^2$ subject to margin constraints) has a dual that depends only on inner products $x_i^\top x_j$, enabling the kernel trick.

**ELBO as a duality gap**: In variational inference, the evidence lower bound ELBO$= \log p(x) - \text{KL}(q \| p(\cdot|x))$ reflects the duality gap between the log-evidence and the variational approximation.

**GANs as minimax**: The GAN objective:
$$\min_G \max_D \mathbb{E}_{x \sim p_{\text{data}}}[\log D(x)] + \mathbb{E}_{z \sim p_z}[\log(1 - D(G(z)))]$$
is a minimax problem. When the discriminator family is rich enough and training dynamics converge, the optimal generator matches the data distribution. In practice, the non-convex-non-concave structure creates training challenges — connecting to [nonconvex-landscapes-saddle-points](nonconvex-landscapes-saddle-points.md).

## Connections

- **Convex analysis**: Duality builds on convexity — see [convex-analysis-separation](convex-analysis-separation.md)
- **Gradient descent**: Primal-dual methods and convergence — see [gradient-descent-convergence](gradient-descent-convergence.md)
- **Online learning**: No-regret learning connects to minimax through game theory — see [online-learning-regret-bounds](online-learning-regret-bounds.md)
- **Game theory**: Minimax is the foundation of zero-sum game theory — see [../game-theory/normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
- **Information theory**: Rate-distortion theory involves Lagrangian duality — see [../information-theory/entropy-source-coding-theorem.md](../information-theory/entropy-source-coding-theorem.md)
