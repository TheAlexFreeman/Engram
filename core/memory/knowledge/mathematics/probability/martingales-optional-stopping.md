---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Martingales and the Optional Stopping Theorem

## Core Idea

A **martingale** is a stochastic process that is, on average, "fair" — its expected future value, given all information so far, equals its current value. Martingales formalise the idea that no strategy can create expected profit from a fair game. The **optional stopping theorem** (Doob) pins down exactly when this fairness persists even when the player chooses when to stop. Martingale theory is the backbone of modern stochastic analysis, providing the mathematical foundation for stochastic integration, derivative pricing, online learning regret bounds, and the Kelly criterion for optimal betting.

---

## Conditional Expectation and Filtrations

### Information Structure

A **filtration** $(\mathcal{F}_n)_{n \geq 0}$ is an increasing sequence of σ-algebras:

$$\mathcal{F}_0 \subseteq \mathcal{F}_1 \subseteq \mathcal{F}_2 \subseteq \cdots \subseteq \mathcal{F}$$

Each $\mathcal{F}_n$ represents the information available at time $n$. A stochastic process $(X_n)$ is **adapted** to $(\mathcal{F}_n)$ if $X_n$ is $\mathcal{F}_n$-measurable for all $n$ — meaning $X_n$ can be determined from information available at time $n$.

### Conditional Expectation

The conditional expectation $\mathbb{E}[X | \mathcal{F}_n]$ is the best $\mathcal{F}_n$-measurable approximation to $X$ in the $L^2$ sense. Key properties:

- **Tower property**: $\mathbb{E}[\mathbb{E}[X | \mathcal{F}_m] | \mathcal{F}_n] = \mathbb{E}[X | \mathcal{F}_n]$ for $n \leq m$
- **Linearity**: $\mathbb{E}[aX + bY | \mathcal{F}] = a\mathbb{E}[X | \mathcal{F}] + b\mathbb{E}[Y | \mathcal{F}]$
- **Pull-out known factors**: If $Y$ is $\mathcal{F}$-measurable, $\mathbb{E}[XY | \mathcal{F}] = Y \cdot \mathbb{E}[X | \mathcal{F}]$
- **Jensen's inequality**: For convex $\varphi$, $\varphi(\mathbb{E}[X | \mathcal{F}]) \leq \mathbb{E}[\varphi(X) | \mathcal{F}]$

The tower property is what makes martingales compositional: it ensures consistency across different levels of information.

---

## Martingales, Submartingales, Supermartingales

### Definitions

An adapted, integrable process $(M_n, \mathcal{F}_n)$ is:

- A **martingale** if $\mathbb{E}[M_{n+1} | \mathcal{F}_n] = M_n$ for all $n$ (fair game)
- A **submartingale** if $\mathbb{E}[M_{n+1} | \mathcal{F}_n] \geq M_n$ for all $n$ (tendency to increase)
- A **supermartingale** if $\mathbb{E}[M_{n+1} | \mathcal{F}_n] \leq M_n$ for all $n$ (tendency to decrease)

### Canonical Examples

**Simple random walk.** Let $X_i$ be i.i.d. with $\mathbb{E}[X_i] = 0$. Then $S_n = \sum_{i=1}^n X_i$ is a martingale.

**Biased random walk.** If $\mathbb{E}[X_i] = \mu > 0$, then $S_n$ is a submartingale but $S_n - n\mu$ is a martingale.

**Exponential martingale.** For i.i.d. $X_i$ with moment generating function $M(\theta) = \mathbb{E}[e^{\theta X_i}]$, the process $\exp(\theta S_n - n \log M(\theta))$ is a martingale. This is the key device behind Chernoff-type concentration bounds (see [concentration-inequalities.md](concentration-inequalities.md)).

**Doob martingale.** For any integrable random variable $Y$ and filtration $(\mathcal{F}_n)$, the process $M_n = \mathbb{E}[Y | \mathcal{F}_n]$ is a martingale. This universal construction means that any prediction problem — updating a forecast as more information arrives — can be cast as a martingale.

**Bayesian posterior.** The posterior probability of a hypothesis given data $D_1, \dots, D_n$ is a martingale under the true data-generating distribution. This formalises the sense in which Bayesian updating is "fair" — you cannot systematically predict which direction the posterior will move.

---

## The Optional Stopping Theorem

### The Gambler's Intuition

If a game is fair (martingale), can a clever stopping strategy generate expected profit? The optional stopping theorem says: under regularity conditions, no.

### Statement (Doob)

Let $(M_n)$ be a martingale and $\tau$ a stopping time with respect to $(\mathcal{F}_n)$. Then $\mathbb{E}[M_\tau] = \mathbb{E}[M_0]$ provided any of:

1. **Bounded stopping time**: $\tau \leq N$ a.s. for some fixed $N$
2. **Bounded martingale**: $|M_{n \wedge \tau}| \leq C$ a.s. for all $n$
3. **Integrable with finite expectation**: $\mathbb{E}[\tau] < \infty$ and there exists $c$ such that $\mathbb{E}[|M_{n+1} - M_n| \,|\, \mathcal{F}_n] \leq c$ a.s.

The conditions are essential. Without them, the theorem fails: the classic **doubling strategy** in gambling (double your bet after each loss) has $\tau$ with infinite expectation and infinite required bankroll, and the conclusion $\mathbb{E}[M_\tau] = \mathbb{E}[M_0]$ does not hold.

### The Wald Identity

A closely related result: if $X_i$ are i.i.d. with $\mathbb{E}[X_i] = \mu$ and $\tau$ is a stopping time with $\mathbb{E}[\tau] < \infty$, then:

$$\mathbb{E}\left[\sum_{i=1}^\tau X_i\right] = \mu \cdot \mathbb{E}[\tau]$$

This is the workhorse of sequential analysis and sequential hypothesis testing (Wald's SPRT).

---

## Martingale Convergence

### Doob's Convergence Theorem

If $(M_n)$ is a submartingale with $\sup_n \mathbb{E}[M_n^+] < \infty$, then $M_n \to M_\infty$ a.s. for some integrable random variable $M_\infty$.

For a non-negative supermartingale (such as a wealth process in a subfair game), convergence is automatic: the process converges almost surely to a non-negative limit.

### Doob's Maximal Inequality

For a non-negative submartingale:

$$\mathbb{P}\left(\max_{0 \leq k \leq n} M_k \geq \lambda\right) \leq \frac{\mathbb{E}[M_n^+]}{\lambda}$$

This controls the probability of large excursions and is the ancestor of all modern maximal concentration results. It directly yields the $L^p$ maximal inequality: $\|\sup_n M_n\|_p \leq \frac{p}{p-1}\|M_n\|_p$ for $p > 1$.

### Doob Decomposition

Any submartingale $X_n$ admits a unique decomposition $X_n = M_n + A_n$ where $M_n$ is a martingale and $A_n$ is a predictable, non-decreasing process with $A_0 = 0$. This separates the "noise" from the "drift" — the pure martingale component from the systematic tendency.

In continuous time, this generalises to the **Doob-Meyer decomposition**, which is the foundation of stochastic calculus (see [stochastic-processes-brownian-sde.md](stochastic-processes-brownian-sde.md)).

---

## Applications

### Online Learning and Regret Analysis

In online convex optimisation, the learner's regret often decomposes as a martingale difference sequence plus a predictable drift. Azuma-Hoeffding's inequality (a martingale concentration bound — see concentration-inequalities.md) gives high-probability regret bounds. The Doob martingale construction converts "average case" guarantees to "individual sequence" guarantees via a martingale-to-stopping-time reduction.

### Gambling and the Kelly Criterion

Kelly (1956) asked: given a favourable bet (submartingale), what fraction of wealth should be wagered at each step to maximise the long-run growth rate? The answer:

$$f^* = \frac{p(b+1) - 1}{b}$$

where $p$ is the win probability and $b$ is the odds ratio. Under Kelly betting, $\log W_n$ (log-wealth) is a submartingale, and the convergence theorem guarantees $W_n \to \infty$ a.s. in the favourable case. The Kelly criterion also connects to information theory: the optimal growth rate equals the mutual information between the side information and the outcome (Cover & Thomas).

### Sequential Hypothesis Testing

Wald's **sequential probability ratio test** (SPRT) uses the log-likelihood ratio $\Lambda_n = \sum_{i=1}^n \log \frac{p_1(X_i)}{p_0(X_i)}$ as a martingale (under $H_0$) or submartingale (under $H_1$). The optional stopping theorem bounds the error probabilities. The SPRT is optimal: among all tests with given error constraints, it minimises the expected sample size (Wald-Wolfowitz theorem).

### Foundations of Stochastic Integration

The Itô integral $\int_0^t H_s \, dW_s$ is defined so that it is a (local) martingale. The martingale representation theorem states that every martingale with respect to the Brownian filtration can be written as such an integral. This is the core of stochastic calculus and the mathematical basis of derivative pricing (Black-Scholes) — see stochastic-processes-brownian-sde.md.

---

## Connections

- **Measure-theoretic probability**: Martingales require the full measure-theoretic conditional expectation — see [measure-theoretic-foundations.md](measure-theoretic-foundations.md)
- **Bayesian inference**: Posterior probabilities form a Doob martingale; the optional stopping theorem implies that Bayesian updating cannot be gamed — see [bayesian-inference-priors-posteriors.md](bayesian-inference-priors-posteriors.md)
- **Ergodic theory**: The Birkhoff ergodic theorem and the martingale convergence theorem are structurally parallel results about long-run averages — see [ergodic-theory-mixing.md](../dynamical-systems/ergodic-theory-mixing.md)
- **Information theory**: The Kelly criterion connects optimal gambling to channel capacity; log-wealth growth rate equals mutual information (Cover & Thomas)
