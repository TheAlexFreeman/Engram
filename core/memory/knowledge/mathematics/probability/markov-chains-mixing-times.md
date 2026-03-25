---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
related: gaussian-processes-bayesian-nonparametrics.md, martingales-optional-stopping.md, measure-theoretic-foundations.md, bayesian-inference-priors-posteriors.md, concentration-inequalities.md, stochastic-processes-brownian-sde.md, ../dynamical-systems/dynamical-systems-fundamentals.md, ../statistical-mechanics/partition-function-free-energy.md
---

# Markov Chains and Mixing Times

## Core Idea

A **Markov chain** is a stochastic process where the future depends on the present but not the past — the simplest model of a system evolving stochastically with memory bounded to the current state. Markov chains are the discrete-time, discrete-state workhorses of applied probability: they model random walks, queueing systems, population genetics, web page ranking (PageRank), and — most critically for computational statistics — they are the engine of **Markov chain Monte Carlo** (MCMC), the principal method for sampling from complex probability distributions. The central quantitative question is: *how long must the chain run before its distribution is close to the stationary (target) distribution?* This is the **mixing time**.

## Definitions and Setup

### Markov property

A sequence of random variables $X_0, X_1, X_2, \ldots$ on a countable state space $S$ is a **Markov chain** if:

$$P(X_{n+1} = j \mid X_n = i, X_{n-1} = i_{n-1}, \ldots, X_0 = i_0) = P(X_{n+1} = j \mid X_n = i)$$

The conditional distribution of the next state depends only on the current state — not on the history.

### Transition matrix

The chain is characterized by its **transition matrix** $\mathbf{P}$ where $P_{ij} = P(X_{n+1} = j \mid X_n = i)$:
- $P_{ij} \geq 0$ for all $i, j$
- $\sum_j P_{ij} = 1$ for all $i$ (rows are probability distributions)

The $n$-step transition probability is $(\mathbf{P}^n)_{ij} = P(X_n = j \mid X_0 = i)$.

If $\mu_0$ is the initial distribution (row vector), then $\mu_n = \mu_0 \mathbf{P}^n$ is the distribution after $n$ steps.

### Classification of states

| Property | Definition |
|----------|-----------|
| **Irreducible** | Every state can be reached from every other state |
| **Aperiodic** | The GCD of return times to each state is 1 |
| **Recurrent** | Starting from $i$, the chain returns to $i$ with probability 1 |
| **Positive recurrent** | Expected return time to $i$ is finite |
| **Ergodic** (for a chain) | Irreducible + aperiodic + positive recurrent |

## Stationary Distributions

### Definition

A probability distribution $\boldsymbol{\pi}$ is **stationary** (or invariant) for the chain if:

$$\boldsymbol{\pi} \mathbf{P} = \boldsymbol{\pi}$$

If the chain is in distribution $\boldsymbol{\pi}$ at time $n$, it remains in distribution $\boldsymbol{\pi}$ at time $n+1$. The chain has reached statistical equilibrium.

### Existence and uniqueness

**Fundamental theorem**: An irreducible, positive recurrent Markov chain has a unique stationary distribution $\boldsymbol{\pi}$, with $\pi_i = 1/\mathbb{E}_i[T_i]$ where $T_i$ is the return time to state $i$.

If the chain is also aperiodic (i.e., ergodic), then:

$$\lim_{n \to \infty} P(X_n = j \mid X_0 = i) = \pi_j \quad \text{for all } i, j$$

The chain converges to the stationary distribution **from any starting state**.

### Detailed balance

A chain satisfies **detailed balance** with respect to $\boldsymbol{\pi}$ if:

$$\pi_i P_{ij} = \pi_j P_{ji} \quad \text{for all } i, j$$

Detailed balance implies $\boldsymbol{\pi}$ is stationary (sum both sides over $j$). A chain satisfying detailed balance is **reversible** — the chain run backward in time has the same transition probabilities. Reversibility is a sufficient (not necessary) condition for stationarity.

## Markov Chain Monte Carlo (MCMC)

### The problem

Given a target distribution $\boldsymbol{\pi}$ (e.g., a Bayesian posterior) that is known only up to a normalizing constant ($\pi_i \propto f(i)$ where $f$ is computable but $\sum_i f(i)$ is not), sample from $\boldsymbol{\pi}$ by constructing a Markov chain whose stationary distribution is $\boldsymbol{\pi}$.

### Metropolis-Hastings algorithm

Given a target $\boldsymbol{\pi}$ and a proposal distribution $Q(j | i)$:

1. At state $i$, propose a move to $j$ with probability $Q(j | i)$.
2. Accept the move with probability:

$$\alpha(i, j) = \min\left(1, \frac{\pi_j Q(i | j)}{\pi_i Q(j | i)}\right)$$

3. If accepted, move to $j$; if rejected, stay at $i$.

The resulting chain satisfies detailed balance with respect to $\boldsymbol{\pi}$:

$$\pi_i Q(j|i) \alpha(i,j) = \pi_j Q(i|j) \alpha(j,i)$$

The normalizing constant of $\boldsymbol{\pi}$ cancels in the acceptance ratio — this is the key computational advantage.

### Gibbs sampling

A special case of Metropolis-Hastings for multivariate distributions. For a target $\pi(x_1, \ldots, x_d)$:

1. At each step, choose a coordinate $k$.
2. Sample $x_k$ from the **conditional distribution** $\pi(x_k \mid x_1, \ldots, x_{k-1}, x_{k+1}, \ldots, x_d)$.

All proposals are accepted (the acceptance ratio is always 1). Gibbs sampling is efficient when the conditional distributions are easy to sample from (e.g., in Bayesian hierarchical models with conjugate priors).

### Hamiltonian Monte Carlo (HMC)

Uses the gradient of $\log \pi$ to make proposals that move along level sets of the target distribution, reducing random-walk behavior. The proposal follows a Hamiltonian trajectory (position = parameters, momentum = auxiliary Gaussian variables):

$$\dot{\mathbf{q}} = \frac{\partial H}{\partial \mathbf{p}}, \quad \dot{\mathbf{p}} = -\frac{\partial H}{\partial \mathbf{q}}, \quad H(\mathbf{q}, \mathbf{p}) = -\log \pi(\mathbf{q}) + \frac{1}{2}\mathbf{p}^T\mathbf{p}$$

HMC proposals move far in parameter space while maintaining high acceptance rates — dramatically improving mixing in high dimensions. It is the engine behind Stan and modern Bayesian computation.

## Mixing Times

### Total variation distance

The **total variation distance** between the chain's distribution at time $n$ (starting from state $i$) and the stationary distribution:

$$d(n) = \max_i \| \mathbf{P}^n(i, \cdot) - \boldsymbol{\pi} \|_{TV} = \max_i \frac{1}{2} \sum_j |P^n(i,j) - \pi_j|$$

### Mixing time

The **mixing time** to accuracy $\epsilon$ is:

$$t_{\text{mix}}(\epsilon) = \min\{n : d(n) \leq \epsilon\}$$

Convention: $t_{\text{mix}} = t_{\text{mix}}(1/4)$ (the choice of $1/4$ is conventional; $t_{\text{mix}}(\epsilon) \leq \lceil \log_2(1/\epsilon) \rceil \cdot t_{\text{mix}}$).

### Spectral gap method

For a reversible chain on a finite state space, the convergence rate is controlled by the **spectral gap**:

$$\gamma = 1 - \lambda_2$$

where $\lambda_2$ is the second-largest eigenvalue of $\mathbf{P}$ (the largest is always 1 for a stochastic matrix). Then:

$$d(n) \leq \frac{1}{2}\sqrt{\frac{1}{\pi_{\min}}} \cdot (1 - \gamma)^n$$

and:

$$\frac{1}{\gamma}\left(\ln \frac{1}{2\epsilon}\right) \leq t_{\text{mix}}(\epsilon) \leq \frac{1}{\gamma}\left(\ln \frac{1}{\pi_{\min}} + \ln \frac{1}{\epsilon}\right)$$

The mixing time is $\Theta(1/\gamma)$ up to logarithmic factors. **Large spectral gap = fast mixing.**

### Conductance (Cheeger's inequality)

The **conductance** (or bottleneck ratio) of a chain:

$$\Phi = \min_{S : \pi(S) \leq 1/2} \frac{\sum_{i \in S, j \notin S} \pi_i P_{ij}}{\pi(S)}$$

measures how easily probability flows between different parts of the state space.

**Cheeger's inequality** relates conductance to the spectral gap:

$$\frac{\Phi^2}{2} \leq \gamma \leq 2\Phi$$

Small conductance (a bottleneck in the state space) implies slow mixing. This is the mathematical diagnosis of multimodality in MCMC — the chain gets trapped in one mode and mixes slowly between modes.

## Examples of Mixing Behavior

### Random walk on a graph

A random walk on a connected, non-bipartite graph (with lazy steps $P_{ii} = 1/2$) has mixing time controlled by the graph's spectral gap:

- **Complete graph** $K_n$: $t_{\text{mix}} = \Theta(\log n)$ (fast).
- **Cycle** $C_n$: $t_{\text{mix}} = \Theta(n^2)$ (slow — random walk must diffuse around the ring).
- **Hypercube** $\{0,1\}^d$: $t_{\text{mix}} = \Theta(d \log d)$ (intermediate; the coupon-collector effect).
- **Expander graphs**: $t_{\text{mix}} = \Theta(\log n)$ (uniformly fast mixing; large spectral gap).

### The cutoff phenomenon

Many natural Markov chains exhibit a **cutoff**: the total variation distance stays near 1 for a long time, then drops to near 0 over a window much shorter than the mixing time. Card shuffling is the classic example — after $\frac{3}{2} n \log n$ riffle shuffles of $n$ cards, the deck is essentially random; before about $n \log n$ shuffles, the deck is far from random. The transition is abrupt.

## Connections to Ergodic Theory

There is a direct analogy between mixing of Markov chains and mixing in ergodic theory:

| Ergodic theory | Markov chains |
|---------------|---------------|
| Invariant measure $\mu$ | Stationary distribution $\boldsymbol{\pi}$ |
| Ergodicity | Irreducibility + recurrence |
| Mixing | Convergence to $\boldsymbol{\pi}$ (aperiodicity + irreducibility) |
| Decay of correlations | Spectral gap, mixing time |
| Birkhoff ergodic theorem | Law of large numbers for Markov chains |

