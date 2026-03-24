---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Stochastic Processes: Brownian Motion, Itô Calculus, and SDEs

## Core Idea

**Brownian motion** (the Wiener process) is the canonical continuous-time stochastic process — the scaling limit of random walks, the driving noise of thermodynamic systems, and the mathematical substrate of modern finance. **Stochastic differential equations** (SDEs) extend ordinary differential equations by adding Brownian noise, but the non-differentiability of Brownian paths forces a fundamentally new calculus: **Itô calculus**. The central object, the **Fokker-Planck equation**, translates an SDE for individual trajectories into a PDE for the evolution of probability densities. This framework directly underpins the free energy principle (Friston's equations are SDEs) and diffusion models in generative AI.

---

## Brownian Motion / Wiener Process

### Definition and Properties

A standard Brownian motion $(W_t)_{t \geq 0}$ satisfies:

1. $W_0 = 0$ a.s.
2. **Independent increments**: $W_t - W_s$ is independent of $\mathcal{F}_s$ for $t > s$
3. **Gaussian increments**: $W_t - W_s \sim \mathcal{N}(0, t-s)$
4. **Continuous paths**: $t \mapsto W_t$ is continuous a.s.

### Fundamental Path Properties

Despite continuity, Brownian paths are extraordinarily rough:

- **Nowhere differentiable**: $\frac{dW}{dt}$ does not exist at any point, a.s.
- **Unbounded variation**: Total variation on any interval $[0, T]$ is infinite
- **Finite quadratic variation**: $\langle W \rangle_T = T$, meaning $\sum_i (W_{t_{i+1}} - W_{t_i})^2 \to T$ as the partition refines
- **Hölder exponent**: Paths are Hölder-$\alpha$ for any $\alpha < 1/2$ but not for $\alpha = 1/2$
- **Fractal dimension**: Brownian paths have Hausdorff dimension 2 in the plane (see [fractals-dimension-multiscale.md](../dynamical-systems/fractals-dimension-multiscale.md))
- **Self-similarity**: $(cW_{t/c^2})_{t \geq 0}$ is again a standard Brownian motion

### Brownian Motion as a Limit

**Donsker's invariance principle** (functional CLT): If $X_i$ are i.i.d. with mean 0 and variance 1, define the interpolated partial sum process $S_n(t) = \frac{1}{\sqrt{n}} S_{\lfloor nt \rfloor}$. Then $S_n \Rightarrow W$ in distribution on $C[0,1]$. This is why Brownian motion appears universally in the continuum limit of random systems.

### Brownian Motion as a Gaussian Process

Brownian motion is a Gaussian process with mean $m(t) = 0$ and covariance $k(s,t) = \min(s,t)$. This connects directly to the GP framework (see [gaussian-processes-bayesian-nonparametrics.md](gaussian-processes-bayesian-nonparametrics.md)): Brownian motion is a GP with a specific kernel.

---

## Itô Calculus

### Why Ordinary Calculus Fails

Since $W_t$ has infinite variation, the Riemann-Stieltjes integral $\int f \, dW$ does not exist in the classical sense. The non-vanishing quadratic variation $dW_t \cdot dW_t = dt$ (informally) means that second-order terms in Taylor expansions cannot be discarded. This gives rise to a fundamentally different calculus.

### The Itô Integral

For an adapted process $H_t$, the Itô integral is defined as:

$$\int_0^T H_t \, dW_t = \lim_{n \to \infty} \sum_i H_{t_i}(W_{t_{i+1}} - W_{t_i})$$

where crucially the integrand is evaluated at the **left** endpoint $t_i$ (non-anticipating). Key properties:

- **Martingale**: $M_t = \int_0^t H_s \, dW_s$ is a (local) martingale
- **Isometry**: $\mathbb{E}\left[\left(\int_0^T H_t \, dW_t\right)^2\right] = \mathbb{E}\left[\int_0^T H_t^2 \, dt\right]$
- **Zero mean**: $\mathbb{E}[\int_0^T H_t \, dW_t] = 0$

The martingale property is the defining feature and connects to the theory in [martingales-optional-stopping.md](martingales-optional-stopping.md).

### Itô's Lemma (the Chain Rule)

For $f(t, X_t)$ where $X_t$ satisfies an SDE, Itô's lemma gives:

$$df = \frac{\partial f}{\partial t} dt + \frac{\partial f}{\partial x} dX_t + \frac{1}{2}\frac{\partial^2 f}{\partial x^2} (dX_t)^2$$

Using the Itô multiplication table $dW \cdot dW = dt$, $dW \cdot dt = 0$, $dt \cdot dt = 0$, this becomes for $dX_t = \mu \, dt + \sigma \, dW_t$:

$$df = \left(\frac{\partial f}{\partial t} + \mu \frac{\partial f}{\partial x} + \frac{\sigma^2}{2}\frac{\partial^2 f}{\partial x^2}\right) dt + \sigma \frac{\partial f}{\partial x} dW_t$$

The extra term $\frac{\sigma^2}{2}\frac{\partial^2 f}{\partial x^2}$ — absent in ordinary calculus — is the Itô correction. It is responsible for, among other things, the drift in geometric Brownian motion and the risk-neutral pricing formula in finance.

### Stratonovich vs Itô

The **Stratonovich integral** evaluates the integrand at the midpoint:

$$\int_0^T H_t \circ dW_t = \lim \sum_i \frac{H_{t_i} + H_{t_{i+1}}}{2}(W_{t_{i+1}} - W_{t_i})$$

Stratonovich calculus obeys ordinary chain rules (no correction term), making it natural for physics (where noise is the limit of smooth processes). Itô calculus is the convention of probability theory and finance (non-anticipating, martingale property). The two are related:

$$\int_0^T H_t \circ dW_t = \int_0^T H_t \, dW_t + \frac{1}{2}\langle H, W \rangle_T$$

---

## Stochastic Differential Equations

### General Form

An SDE has the form:

$$dX_t = \mu(X_t, t) \, dt + \sigma(X_t, t) \, dW_t$$

where $\mu$ is the **drift** (deterministic tendency) and $\sigma$ is the **diffusion** (noise amplitude). Under Lipschitz and linear growth conditions on $\mu$ and $\sigma$, a unique strong solution exists.

### Important Examples

**Geometric Brownian motion** (GBM): $dS_t = \mu S_t \, dt + \sigma S_t \, dW_t$. Solution via Itô's lemma: $S_t = S_0 \exp((\mu - \sigma^2/2)t + \sigma W_t)$. The standard model for stock prices (Black-Scholes).

**Ornstein-Uhlenbeck process**: $dX_t = -\theta X_t \, dt + \sigma \, dW_t$. Mean-reverting Gaussian process. The stationary distribution is $\mathcal{N}(0, \sigma^2 / 2\theta)$. This is the continuous-time analogue of an AR(1) process and appears in physics as the velocity of a Brownian particle under friction (Langevin equation).

**Langevin dynamics**: $dX_t = -\nabla U(X_t) \, dt + \sqrt{2\beta^{-1}} \, dW_t$. Under regularity conditions, the stationary distribution is the Boltzmann-Gibbs measure $p(x) \propto e^{-\beta U(x)}$. This is the bridge between SDEs and statistical mechanics, and the basis of Langevin MCMC methods (see [markov-chains-mixing-times.md](markov-chains-mixing-times.md)).

---

## The Fokker-Planck Equation

### From Trajectories to Densities

Given the SDE $dX_t = \mu(X_t) \, dt + \sigma(X_t) \, dW_t$, the probability density $p(x, t)$ of $X_t$ evolves according to the **Fokker-Planck** (or Kolmogorov forward) equation:

$$\frac{\partial p}{\partial t} = -\frac{\partial}{\partial x}[\mu(x) p] + \frac{1}{2}\frac{\partial^2}{\partial x^2}[\sigma^2(x) p]$$

The first term is advection (drift), the second is diffusion (spreading). In the multivariate case with $\mathbf{\Sigma} = \sigma \sigma^\top$:

$$\frac{\partial p}{\partial t} = -\nabla \cdot (\boldsymbol{\mu} \, p) + \frac{1}{2}\nabla \cdot (\mathbf{\Sigma} \nabla p)$$

### Stationary Solutions

Setting $\partial p / \partial t = 0$ gives the stationary (equilibrium) density. For Langevin dynamics with $\mu = -\nabla U$ and constant $\sigma = \sqrt{2\beta^{-1}}$:

$$p_{\text{eq}}(x) = \frac{1}{Z} e^{-\beta U(x)}, \quad Z = \int e^{-\beta U(x)} dx$$

This is the Boltzmann distribution. The partition function $Z$ normalises the density. This connection between SDEs and equilibrium statistical mechanics is the mathematical basis for energy-based models in machine learning.

### The Kolmogorov Backward Equation

The dual equation governs expectations of functions of the terminal state:

$$\frac{\partial u}{\partial t} + \mu \frac{\partial u}{\partial x} + \frac{\sigma^2}{2}\frac{\partial^2 u}{\partial x^2} = 0$$

where $u(x, t) = \mathbb{E}[f(X_T) | X_t = x]$. The backward equation is the basis of the Feynman-Kac formula, which connects SDEs to PDEs and enables probabilistic solutions to partial differential equations.

---

## Bridge to the Free Energy Principle

Friston's free energy principle models biological agents as stochastic dynamical systems. The core mathematical framework is:

1. **Langevin dynamics**: Internal states evolve via $d\mathbf{x}_t = f(\mathbf{x}_t) \, dt + \sigma \, dW_t$
2. **Fokker-Planck equation**: The density over states evolves towards a steady-state (the "attracting set" or Markov blanket)
3. **Variational free energy**: The agent's belief $q(\mathbf{x})$ approximates the true posterior by minimising $F = \mathbb{E}_q[\log q - \log p] = D_\text{KL}(q \| p) + \text{const}$

The gradient flow that minimises variational free energy is itself an SDE, closing the loop: the agent is a stochastic dynamical system whose dynamics minimise surprise (negative log evidence).

---

## Bridge to Diffusion Models in Generative AI

Score-based diffusion models (Song & Ermon, 2019; Ho et al., 2020) directly implement SDE theory:

1. **Forward process**: A data distribution $p_{\text{data}}$ is progressively noised via a forward SDE: $dX_t = f(X_t, t) \, dt + g(t) \, dW_t$, transforming data to Gaussian noise
2. **Reverse process**: Anderson (1982) showed the time-reversed SDE is $dX_t = [f - g^2 \nabla_x \log p_t(X_t)] \, dt + g(t) \, d\bar{W}_t$, which requires the **score function** $\nabla_x \log p_t$
3. **Score matching**: A neural network learns to approximate the score, enabling sampling by simulating the reverse SDE from noise to data

The probability flow ODE (a deterministic version of the reverse SDE) connects diffusion models to continuous normalising flows. The Fokker-Planck equation governs the density evolution in both directions, ensuring that generation and likelihood evaluation are mathematically consistent.

---

## Connections

- **Measure-theoretic foundations**: SDE solutions are defined as random variables on probability spaces; the Girsanov theorem changes the drift by changing the measure — see [measure-theoretic-foundations.md](measure-theoretic-foundations.md)
- **Ergodic theory**: The long-time behaviour of SDEs (mixing times, convergence to stationary distributions) is governed by ergodic properties — see [ergodic-theory-mixing.md](../dynamical-systems/ergodic-theory-mixing.md)
- **Dynamical systems**: SDEs are noisy dynamical systems; the Fokker-Planck equation describes the evolution of densities on phase space — see [dynamical-systems-fundamentals.md](../dynamical-systems/dynamical-systems-fundamentals.md)
