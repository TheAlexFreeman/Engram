---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
related: bayesian-inference-priors-posteriors.md, measure-theoretic-foundations.md, stochastic-processes-brownian-sde.md, gaussian-processes-bayesian-nonparametrics.md, markov-chains-mixing-times.md, martingales-optional-stopping.md, ../statistical-mechanics/hopfield-boltzmann-machines.md, ../statistical-mechanics/ising-model-phase-transitions.md
---

# Concentration Inequalities

## Core Idea

**Concentration inequalities** bound the probability that a random variable deviates from some "typical" value (usually its mean) by more than a specified amount. They are the sharp, finite-sample tools that make learning theory Work — converting the qualitative intuition "averages converge" (law of large numbers) into quantitative statements "the average is within $\epsilon$ of the mean with probability at least $1 - \delta$, given $n$ samples." Every PAC bound, every generalization guarantee, and every sample complexity result rests on concentration inequalities.

## The Basic Hierarchy

### Markov's inequality

The simplest and most general — requires only non-negativity and finite expectation.

For $X \geq 0$ and $t > 0$:

$$P(X \geq t) \leq \frac{\mathbb{E}[X]}{t}$$

Strength: applies to any non-negative random variable. Weakness: the bound is loose — it cannot be better than $1/t$ regardless of the distribution.

### Chebyshev's inequality

Applies Markov to $(X - \mu)^2$, requiring finite variance.

For any $X$ with $\mathbb{E}[X] = \mu$ and $\text{Var}(X) = \sigma^2$:

$$P(|X - \mu| \geq t) \leq \frac{\sigma^2}{t^2}$$

Equivalently, for $k$ standard deviations: $P(|X - \mu| \geq k\sigma) \leq 1/k^2$.

This gives polynomial tail decay ($1/t^2$). Better than Markov but still far from the exponential decay of sub-Gaussian distributions.

### Chernoff bound (exponential moment method)

The Chernoff bound applies the exponential function to turn tail bounds into moment-generating function (MGF) bounds:

$$P(X \geq t) = P(e^{sX} \geq e^{st}) \leq \frac{\mathbb{E}[e^{sX}]}{e^{st}} \quad \text{for any } s > 0$$

Optimizing over $s$ gives the tightest bound. For sums of independent random variables, the MGF factors:

$$\mathbb{E}[e^{s\sum_i X_i}] = \prod_i \mathbb{E}[e^{sX_i}]$$

This factoring is the engine of all sharp exponential concentration bounds.

## Sub-Gaussian Variables

### Definition

A centered random variable $X$ (with $\mathbb{E}[X] = 0$) is **$\sigma$-sub-Gaussian** if:

$$\mathbb{E}[e^{sX}] \leq e^{s^2\sigma^2/2} \quad \text{for all } s \in \mathbb{R}$$

Equivalently, its tails decay at least as fast as a Gaussian with variance $\sigma^2$:

$$P(|X| \geq t) \leq 2e^{-t^2/(2\sigma^2)}$$

### Examples

- Any bounded random variable $X \in [a, b]$ is $(b-a)/2$-sub-Gaussian (by Hoeffding's lemma).
- A Gaussian $\mathcal{N}(0, \sigma^2)$ is $\sigma$-sub-Gaussian (the definition is calibrated to this case).
- Rademacher variables ($\pm 1$ with equal probability) are 1-sub-Gaussian.

Sub-Gaussian concentration is the "default" tail behavior in learning theory.

## Hoeffding's Inequality

### Statement

If $X_1, \ldots, X_n$ are independent with $X_i \in [a_i, b_i]$:

$$P\left(\left|\frac{1}{n}\sum_{i=1}^n X_i - \frac{1}{n}\sum_{i=1}^n \mathbb{E}[X_i]\right| \geq t\right) \leq 2\exp\left(-\frac{2n^2 t^2}{\sum_{i=1}^n (b_i - a_i)^2}\right)$$

For identically bounded variables ($a_i = a$, $b_i = b$):

$$P\left(|\bar{X}_n - \mu| \geq t\right) \leq 2\exp\left(-\frac{2nt^2}{(b-a)^2}\right)$$

### Significance

Hoeffding's inequality is the workhorse of PAC learning. It says: the sample mean of $n$ bounded independent observations is within $\epsilon$ of the true mean with probability at least $1 - \delta$, provided:

$$n \geq \frac{(b-a)^2}{2\epsilon^2} \ln \frac{2}{\delta}$$

This gives the **sample complexity** for estimating a bounded mean to accuracy $\epsilon$ with confidence $1 - \delta$. The $O(1/\epsilon^2)$ dependence and $O(\ln(1/\delta))$ dependence are characteristic.

## McDiarmid's Inequality (Bounded Differences)

### Statement

If $f: \mathcal{X}^n \to \mathbb{R}$ satisfies the **bounded differences condition**:

$$\sup_{x_1, \ldots, x_n, x_i'} |f(x_1, \ldots, x_i, \ldots, x_n) - f(x_1, \ldots, x_i', \ldots, x_n)| \leq c_i$$

for each $i$, and $X_1, \ldots, X_n$ are independent, then:

$$P(f(X_1, \ldots, X_n) - \mathbb{E}[f] \geq t) \leq \exp\left(-\frac{2t^2}{\sum_{i=1}^n c_i^2}\right)$$

### Significance

McDiarmid generalizes Hoeffding to **any function of independent variables that doesn't depend too much on any single variable**. This is crucial for learning theory: the empirical risk $\hat{R}(h) = \frac{1}{n}\sum_i \ell(h(x_i), y_i)$ is a function of the training data; if the loss is bounded, then changing one training point changes $\hat{R}$ by at most $c_i = 1/n$, so McDiarmid gives exponential concentration of empirical risk around expected risk.

This is the key inequality underlying the **uniform convergence** arguments in PAC learning: not just one function concentrates, but all functions in a hypothesis class concentrate simultaneously (via a union bound over the VC dimension or covering number).

## Martingale Concentration: Azuma-Hoeffding

### Statement

If $(M_0, M_1, \ldots, M_n)$ is a martingale with bounded increments $|M_i - M_{i-1}| \leq c_i$:

$$P(|M_n - M_0| \geq t) \leq 2\exp\left(-\frac{t^2}{2\sum_{i=1}^n c_i^2}\right)$$

### Significance

Azuma-Hoeffding extends concentration to **dependent** random variables — specifically, to martingale sequences (which include sums of independent variables as a special case). The Doob martingale construction allows extending any McDiarmid-style analysis to more complex dependence structures.

Application: In a tournament of $n$ games, with an individual's score as a martingale, the total score is concentrated around its expected value even though individual game outcomes may depend on previous results (through the martingale structure).

## Bernstein's and Bennett's Inequalities

### Bernstein's inequality

For independent centered random variables with $|X_i| \leq M$ and $\sum_i \text{Var}(X_i) = V$:

$$P\left(\sum_i X_i \geq t\right) \leq \exp\left(-\frac{t^2/2}{V + Mt/3}\right)$$

Bernstein interpolates between sub-Gaussian behavior (when $t$ is small: the bound is $\sim \exp(-t^2/2V)$, depending on variance) and sub-exponential behavior (when $t$ is large: $\sim \exp(-t/M)$, depending on the bound). It is tighter than Hoeffding when the variance is much smaller than the worst-case range.

### Application to sparse problems

In high-dimensional statistics, variables often have small variance but potentially large support. Bernstein's inequality gives sharper bounds in this regime than Hoeffding (which ignores variance information).

## Matrix Concentration

### Matrix Bernstein inequality

For independent random matrices $\mathbf{X}_i$ with $\mathbb{E}[\mathbf{X}_i] = \mathbf{0}$ and $\|\mathbf{X}_i\| \leq R$:

$$P\left(\left\|\sum_i \mathbf{X}_i\right\| \geq t\right) \leq (d_1 + d_2) \exp\left(-\frac{t^2/2}{\sigma^2 + Rt/3}\right)$$

where $\sigma^2 = \max\{\|\sum_i \mathbb{E}[\mathbf{X}_i \mathbf{X}_i^T]\|, \|\sum_i \mathbb{E}[\mathbf{X}_i^T \mathbf{X}_i]\|\}$.

Matrix concentration is essential for random matrix theory, covariance estimation, and the analysis of randomized algorithms in machine learning (random features, sketching, compressed sensing).

## Application to Learning Theory

### Sample complexity via concentration

The standard PAC learning argument:

1. Fix a hypothesis $h$. The empirical risk $\hat{R}(h)$ concentrates around the true risk $R(h)$ by Hoeffding: $P(|\hat{R}(h) - R(h)| > \epsilon) \leq 2e^{-2n\epsilon^2}$.
2. Take a **union bound** over all hypotheses in a finite class $|\mathcal{H}|$: $P(\exists h : |\hat{R}(h) - R(h)| > \epsilon) \leq 2|\mathcal{H}|e^{-2n\epsilon^2}$.
3. Set the right side $\leq \delta$ and solve for $n$: $n \geq \frac{1}{2\epsilon^2}\ln\frac{2|\mathcal{H}|}{\delta}$.

For infinite hypothesis classes, replace $|\mathcal{H}|$ with covering numbers or VC dimension, yielding the fundamental theorem of statistical learning.

### Rademacher complexity

Rademacher complexity provides a data-dependent concentration bound. For a function class $\mathcal{F}$:

$$\hat{\mathfrak{R}}_n(\mathcal{F}) = \mathbb{E}_\sigma\left[\sup_{f \in \mathcal{F}} \frac{1}{n}\sum_{i=1}^n \sigma_i f(X_i)\right]$$

where $\sigma_i$ are i.i.d. Rademacher variables. McDiarmid's inequality applied to the Rademacher complexity gives: with probability $\geq 1 - \delta$:

$$\sup_{f \in \mathcal{F}} |R(f) - \hat{R}(f)| \leq 2\hat{\mathfrak{R}}_n(\mathcal{F}) + 3\sqrt{\frac{\ln(2/\delta)}{2n}}$$

