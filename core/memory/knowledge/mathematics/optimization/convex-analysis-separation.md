---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Convex Analysis and Separation Theorems

## Core Idea

Convexity is the single most powerful structural assumption in optimisation: a convex problem has no spurious local minima, every local minimum is global, and strong duality typically holds. The theory of convex sets and functions, culminating in the separation and supporting hyperplane theorems (finite-dimensional instances of Hahn-Banach), provides the geometric and analytic foundation for linear programming, semidefinite programming, and the entire edifice of convex optimisation that underpins modern machine learning.

## Convex Sets

A set $C \subseteq \mathbb{R}^n$ is **convex** if for all $x, y \in C$ and $\lambda \in [0, 1]$:
$$\lambda x + (1 - \lambda) y \in C$$

**Key operations preserving convexity**:
- Intersection: $\bigcap_\alpha C_\alpha$ is convex if each $C_\alpha$ is
- Affine image and preimage: $f(C) = \{Ax + b : x \in C\}$
- Minkowski sum: $C_1 + C_2 = \{x + y : x \in C_1, y \in C_2\}$
- Perspective and linear-fractional maps

**Extreme points and Krein-Milman**: An *extreme point* of a convex set $C$ is a point that cannot be written as a strict convex combination of other points in $C$. The **Krein-Milman theorem**: every compact convex set is the closed convex hull of its extreme points. This is the foundation for the simplex method — optimal LP solutions occur at vertices (extreme points) of the feasible polytope.

**Convex hull**: $\text{conv}(S) = \{\sum_{i=1}^k \lambda_i x_i : x_i \in S, \lambda_i \geq 0, \sum \lambda_i = 1\}$. By Carathéodory's theorem, in $\mathbb{R}^n$, every point in $\text{conv}(S)$ is a convex combination of at most $n + 1$ points of $S$.

## Convex Functions

$f : \mathbb{R}^n \to \mathbb{R} \cup \{+\infty\}$ is **convex** if:
$$f(\lambda x + (1 - \lambda)y) \leq \lambda f(x) + (1 - \lambda) f(y), \quad \forall \lambda \in [0, 1]$$

Equivalently, the **epigraph** $\text{epi}(f) = \{(x, t) : f(x) \leq t\}$ is a convex set.

**First-order condition** (for differentiable $f$):
$$f(y) \geq f(x) + \nabla f(x)^\top (y - x), \quad \forall x, y$$

The tangent hyperplane is a global under-estimator — this is why gradient descent works for convex functions.

**Second-order condition**: $f$ is convex iff $\nabla^2 f(x) \succeq 0$ (positive semidefinite Hessian) for all $x$.

**Strong convexity**: $f$ is $\mu$-strongly convex if $f(x) - \frac{\mu}{2}\|x\|^2$ is convex. Equivalently, $\nabla^2 f(x) \succeq \mu I$. Strong convexity provides exponential convergence guarantees for gradient descent.

### Important Examples

| Function | Domain | Properties |
|----------|--------|-----------|
| $\|x\|^2$ | $\mathbb{R}^n$ | Strongly convex ($\mu = 2$) |
| $\|x\|_1$ | $\mathbb{R}^n$ | Convex, non-smooth |
| $-\log x$ | $\mathbb{R}_{++}$ | Strictly convex, self-concordant |
| $\log \det X^{-1}$ | $S^n_{++}$ | Convex on positive definite matrices |
| $e^x$ | $\mathbb{R}$ | Convex |
| $x \log x$ | $\mathbb{R}_+$ | Strictly convex (neg-entropy) |
| $\text{KL}(p \| q)$ | Probability simplex | Jointly convex |

## Separation Theorems

### Supporting Hyperplane Theorem

If $C$ is convex and $x_0 \in \partial C$ (boundary), then there exists a nonzero $a \in \mathbb{R}^n$ such that:
$$a^\top x \leq a^\top x_0, \quad \forall x \in C$$

The hyperplane $\{x : a^\top x = a^\top x_0\}$ "supports" $C$ at $x_0$ — it touches $C$ without crossing into its interior.

### Separating Hyperplane Theorem

If $C, D$ are disjoint convex sets, there exists $a \neq 0$ and $b$ such that:
$$a^\top x \leq b \leq a^\top y, \quad \forall x \in C, y \in D$$

**Strict separation**: If $C$ is closed and $D$ is compact (and disjoint), then strict inequality holds.

### Hahn-Banach (Infinite-Dimensional Extension)

In a normed space $X$: if $C$ is convex, open, and $x_0 \notin C$, then there exists a continuous linear functional separating $x_0$ from $C$. This is the *geometric form* of the Hahn-Banach theorem.

Applications in optimisation:
- Every linear program has a dual (via separation)
- KKT conditions arise from separating the feasible set from the improving direction set
- Farkas' lemma (and alternatives theorems) are consequences of separation

## Subdifferentials and Non-Smooth Analysis

For non-differentiable convex $f$, the **subdifferential** at $x$ is:
$$\partial f(x) = \{g \in \mathbb{R}^n : f(y) \geq f(x) + g^\top(y - x), \; \forall y\}$$

Each $g \in \partial f(x)$ is a *subgradient*. Properties:
- $\partial f(x) \neq \emptyset$ for all $x$ in the relative interior of $\text{dom}(f)$
- $0 \in \partial f(x^*) \iff x^*$ is a global minimiser
- If $f$ is differentiable at $x$, then $\partial f(x) = \{\nabla f(x)\}$

**Example**: $f(x) = |x|$ has $\partial f(0) = [-1, 1]$. The subgradient method generalises gradient descent to non-smooth convex problems.

**Proximal operators**: For non-smooth but structured $f$ (e.g., $\ell_1$ regularisation):
$$\text{prox}_f(x) = \arg\min_u \left\{f(u) + \frac{1}{2}\|u - x\|^2\right\}$$

Proximal gradient methods (ISTA, FISTA) combine gradient steps on smooth terms with proximal steps on non-smooth terms — central to sparse optimisation and LASSO.

## Convex Optimisation Problems

The general form:
$$\min_{x} f_0(x) \quad \text{s.t.} \quad f_i(x) \leq 0, \; i = 1, \ldots, m; \quad h_j(x) = 0, \; j = 1, \ldots, p$$

where $f_0, f_1, \ldots, f_m$ are convex and $h_1, \ldots, h_p$ are affine.

**Hierarchy of tractability**:
1. **Linear programs** (LP): linear objective and constraints. Solved in polynomial time (ellipsoid, interior point).
2. **Quadratic programs** (QP): quadratic objective, linear constraints.
3. **Second-order cone programs** (SOCP): generalise LP and QP.
4. **Semidefinite programs** (SDP): optimise over the cone of positive semidefinite matrices. Solve MAX-CUT relaxation (Goemans-Williamson).
5. **General convex**: polynomial-time via ellipsoid method (Grötschel-Lovász-Schrijver) or interior point methods.

$$\text{LP} \subset \text{QP} \subset \text{SOCP} \subset \text{SDP} \subset \text{Convex}$$

## Self-Concordance and Interior Point Methods

**Nesterov-Nemirovski** (1994): Interior point methods solve convex optimisation problems with $m$ constraints in $O(\sqrt{m} \log(1/\varepsilon))$ Newton steps, each costing $O(m^2 n + n^3)$ arithmetic operations.

The key concept is **self-concordance**: a function $f$ is self-concordant if $|f'''(x)| \leq 2(f''(x))^{3/2}$. The **barrier function** $-\sum_i \log(-f_i(x))$ is self-concordant, enabling Newton's method to converge with predictable step sizes.

This framework provides a *unified* polynomial-time algorithm for all convex programs — one of the most elegant results in continuous optimisation.

## Connections

- **Duality theory**: Lagrange duality and minimax theorems extend convex analysis — see [duality-theory-minimax](duality-theory-minimax.md)
- **Gradient descent**: Convergence analysis depends on convexity and smoothness — see [gradient-descent-convergence](gradient-descent-convergence.md)
- **Game theory**: Nash equilibria as fixed points of best-response correspondences over convex strategy sets — see [../game-theory/normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
- **Information theory**: KL divergence is convex; MaxEnt is a convex program — see [../information-theory/entropy-source-coding-theorem.md](../information-theory/entropy-source-coding-theorem.md)
- **Statistical mechanics**: Free energy minimisation is a convex problem in the variational formulation — see [../statistical-mechanics/partition-function-free-energy.md](../statistical-mechanics/partition-function-free-energy.md)
- **Concentration inequalities**: Convexity appears in martingale and measure concentration results — see [../probability/concentration-inequalities.md](../probability/concentration-inequalities.md)
