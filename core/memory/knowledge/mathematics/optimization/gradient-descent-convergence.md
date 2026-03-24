---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Gradient Descent and Convergence Theory

## Core Idea

Gradient descent is the workhorse of continuous optimisation: iterate $x_{t+1} = x_t - \eta \nabla f(x_t)$ and converge to a minimum. The convergence rate depends sharply on the function's *convexity* and *smoothness* — characterised by the condition number $\kappa = L/\mu$. Stochastic gradient descent (SGD) trades per-iteration cost for noise, yet achieves optimal rates for convex problems and implicitly regularises in the non-convex setting of deep learning. Acceleration (Nesterov momentum) achieves provably optimal rates for first-order methods.

## Gradient Descent (GD) for Smooth Convex Functions

**Setup**: Minimise $f : \mathbb{R}^n \to \mathbb{R}$, where $f$ is convex and **$L$-smooth**: $\|\nabla f(x) - \nabla f(y)\| \leq L\|x - y\|$ for all $x, y$.

Equivalently, $-LI \preceq \nabla^2 f(x) \preceq LI$ (bounded curvature).

**Update**: $x_{t+1} = x_t - \eta \nabla f(x_t)$ with step size $\eta = 1/L$.

### Convergence Rates

| Assumption | Rate | Bound |
|-----------|------|-------|
| Convex, $L$-smooth | $O(1/t)$ | $f(x_t) - f^* \leq \frac{L\|x_0 - x^*\|^2}{2t}$ |
| $\mu$-strongly convex, $L$-smooth | $O((1 - \mu/L)^t)$ | Linear (exponential) convergence |
| Lipschitz (non-smooth) | $O(1/\sqrt{t})$ | With $\eta_t = O(1/\sqrt{t})$ |

**Condition number** $\kappa = L/\mu$: For strongly convex functions, GD converges in $O(\kappa \log(1/\varepsilon))$ iterations. Ill-conditioned problems ($\kappa \gg 1$) converge slowly — this motivates preconditioning and acceleration.

### Proof Sketch (Convex, $L$-Smooth)

From $L$-smoothness:
$$f(x_{t+1}) \leq f(x_t) + \nabla f(x_t)^\top(x_{t+1} - x_t) + \frac{L}{2}\|x_{t+1} - x_t\|^2$$

With $\eta = 1/L$:
$$f(x_{t+1}) \leq f(x_t) - \frac{1}{2L}\|\nabla f(x_t)\|^2$$

Combined with convexity $f(x^*) \geq f(x_t) + \nabla f(x_t)^\top(x^* - x_t)$, a telescoping argument yields the $O(1/t)$ rate.

## Nesterov Acceleration

**Nesterov's accelerated gradient** (1983):
$$y_t = x_t + \frac{t-1}{t+2}(x_t - x_{t-1})$$
$$x_{t+1} = y_t - \frac{1}{L}\nabla f(y_t)$$

### Accelerated Rates

| Assumption | GD Rate | Accelerated Rate |
|-----------|---------|-----------------|
| Convex, $L$-smooth | $O(1/t)$ | $O(1/t^2)$ |
| $\mu$-strongly convex | $O((1 - 1/\kappa)^t)$ | $O((1 - 1/\sqrt{\kappa})^t)$ |

The acceleration from $O(\kappa)$ to $O(\sqrt{\kappa})$ iterations for strongly convex functions can be enormous for ill-conditioned problems.

**Optimality**: Nesterov (1983) proved matching lower bounds — no first-order method (using only gradient oracle queries) can achieve better rates for the class of $L$-smooth convex functions. The accelerated rate is *optimal*.

**Interpretation**: The momentum term $\frac{t-1}{t+2}(x_t - x_{t-1})$ introduces *inertia*, causing the iterate to "overshoot" in a controlled way. The continuous-time limit $\ddot{x} + \frac{3}{t}\dot{x} + \nabla f(x) = 0$ (Su-Boyd-Candès 2016) is a damped oscillator ODE, connecting acceleration to dynamical systems.

## Stochastic Gradient Descent (SGD)

**Setup**: Minimise $f(x) = \mathbb{E}_{\xi}[f(x; \xi)]$ where each $f(\cdot; \xi)$ is a loss on a data sample.

**SGD update**: $x_{t+1} = x_t - \eta_t \nabla f(x_t; \xi_t)$ where $\xi_t$ is a random sample.

Key property: $\mathbb{E}[\nabla f(x; \xi)] = \nabla f(x)$ — unbiased gradient estimates.

### SGD Convergence Rates

| Setting | Step Size | Rate |
|---------|-----------|------|
| Convex, $L$-smooth | $\eta_t = O(1/\sqrt{t})$ | $O(1/\sqrt{t})$ |
| $\mu$-strongly convex | $\eta_t = O(1/(\mu t))$ | $O(1/(\mu t))$ |
| Non-convex, $L$-smooth | $\eta_t = O(1/\sqrt{t})$ | $\mathbb{E}\|\nabla f(x_t)\|^2 = O(1/\sqrt{t})$ |

**Variance bound**: If $\mathbb{E}\|\nabla f(x; \xi) - \nabla f(x)\|^2 \leq \sigma^2$, then:
$$\mathbb{E}[f(\bar{x}_t)] - f^* \leq O\left(\frac{\|x_0 - x^*\|^2}{t} + \frac{\sigma}{\sqrt{t}}\right)$$

The $O(1/\sqrt{t})$ rate is *optimal* for stochastic first-order methods (information-theoretic lower bound). The noise floor $\sigma/\sqrt{t}$ cannot be improved without variance reduction.

### Variance Reduction

Methods that achieve linear convergence for finite sums $f(x) = \frac{1}{n}\sum_{i=1}^n f_i(x)$:

- **SVRG** (Johnson-Zhang 2013): Periodically compute full gradient; use as control variate
- **SAGA** (Defazio et al. 2014): Maintain table of individual gradients
- **SARAH/STORM**: Recursive variance reduction for online settings

These achieve $O((n + \kappa)\log(1/\varepsilon))$ convergence — near the cost of $n$ gradient evaluations per epoch, matching full GD rate with per-iteration cost of SGD.

## Learning Rate Schedules

The choice of learning rate schedule $\{\eta_t\}$ profoundly affects both convergence speed and final performance:

| Schedule | Formula | Properties |
|----------|---------|-----------|
| Constant | $\eta_t = \eta$ | Converges to neighbourhood of optimum (radius $\propto \eta\sigma^2$) |
| $1/t$ decay | $\eta_t = c/t$ | Optimal for strongly convex; slow in practice |
| $1/\sqrt{t}$ decay | $\eta_t = c/\sqrt{t}$ | Optimal for convex |
| Step decay | $\eta_t = \eta_0 \cdot \gamma^{\lfloor t/T \rfloor}$ | Common in deep learning |
| Cosine annealing | $\eta_t = \frac{\eta_0}{2}(1 + \cos(\pi t/T))$ | Smooth warm restart |
| Linear warmup | $\eta_t = \eta_0 \cdot \min(t/T_w, 1)$ | Stabilises early training |

**Robbins-Monro conditions**: $\sum \eta_t = \infty$ and $\sum \eta_t^2 < \infty$ guarantee asymptotic convergence but not a particular rate.

## Adaptive Methods

Methods that adapt the learning rate per-coordinate:

- **AdaGrad** (Duchi et al. 2011): $\eta_{t,i} = \eta / \sqrt{\sum_{s=1}^t g_{s,i}^2}$. Optimal for sparse gradients; diminishing rates kill performance on non-sparse problems.
- **RMSProp** (Hinton): Exponential moving average of squared gradients — fixes AdaGrad's decay.
- **Adam** (Kingma-Ba 2015): Combines momentum ($\beta_1$) with RMSProp-style scaling ($\beta_2$). Bias-corrected estimates: $\hat{m}_t = m_t/(1 - \beta_1^t)$, $\hat{v}_t = v_t/(1 - \beta_2^t)$.
- **AdamW** (Loshchilov-Hutter 2019): Decoupled weight decay — fixes Adam's interaction with $L^2$ regularisation.

**Theory vs practice tension**: Adam can diverge for some convex problems (Reddi et al. 2018), yet works excellently in practice. AMSGrad provides convergence guarantees by maintaining the maximum of past $v_t$ values.

## Implicit Regularisation of SGD

A remarkable empirical and theoretical observation: SGD with large learning rates finds *flatter* minima that generalise better.

**Mechanisms**:
- **Label noise as regularisation**: SGD noise is proportional to learning rate × batch gradient covariance. Larger noise escapes sharp minima.
- **Stochastic differential equation (SDE) approximation**: In the continuous-time limit, SGD approximates $dx = -\nabla f(x) dt + \sqrt{\eta \Sigma(x)} dW_t$. The diffusion term $\Sigma(x)$ depends on local loss curvature, biasing dynamics toward flat regions.
- **Edge of stability** (Cohen et al. 2021): With large constant learning rates, GD operates at the "edge of stability" where the maximum eigenvalue of the Hessian hovers near $2/\eta$, self-tuning curvature.

This connects to the generalisation puzzle in deep learning — see [nonconvex-landscapes-saddle-points](nonconvex-landscapes-saddle-points.md).

## Connections

- **Convex analysis**: Convergence theory depends on convexity and smoothness properties — see [convex-analysis-separation](convex-analysis-separation.md)
- **Duality**: Primal-dual gradient methods — see [duality-theory-minimax](duality-theory-minimax.md)
- **Online learning**: SGD as online convex optimisation — see [online-learning-regret-bounds](online-learning-regret-bounds.md)
- **Dynamical systems**: Continuous-time limits of optimisation algorithms are ODEs — see [../dynamical-systems/dynamical-systems-fundamentals.md](../dynamical-systems/dynamical-systems-fundamentals.md)
- **Stochastic processes**: SGD noise ≈ Brownian motion — see [../probability/stochastic-processes-brownian-sde.md](../probability/stochastic-processes-brownian-sde.md)
- **Statistical mechanics of learning**: Phase transitions in optimisation landscapes — see [../statistical-mechanics/statistical-mechanics-of-learning.md](../statistical-mechanics/statistical-mechanics-of-learning.md)
