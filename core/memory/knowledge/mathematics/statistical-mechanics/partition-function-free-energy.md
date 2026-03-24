---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# The Partition Function, Free Energy, and Variational Principles

## Core Idea

The **partition function** $Z$ is the central object of statistical mechanics — a normalising sum over all possible states that encodes the entire thermodynamics of a system. The **free energy** $F = -k_B T \ln Z$ is its logarithmic transform, connecting microscopic state counting to macroscopic work and equilibrium. The variational formulation of free energy — minimising an energy-entropy trade-off over distributions — is the mathematical template for variational inference, energy-based models in deep learning, and Friston's free energy principle.

---

## The Canonical Ensemble

### Setup

Consider a system in thermal contact with a heat bath at temperature $T$. The system has microstates $\{s\}$ with energies $\{E(s)\}$. The maximum entropy distribution compatible with fixed average energy $\langle E \rangle$ is the **Boltzmann distribution**:

$$p(s) = \frac{1}{Z} e^{-\beta E(s)}, \quad \beta = \frac{1}{k_B T}$$

### The Partition Function

The normalisation constant is the **partition function**:

$$Z(\beta) = \sum_s e^{-\beta E(s)}$$

(For continuous state spaces, replace the sum with an integral.) Despite being "just normalisation," $Z$ contains all thermodynamic information. Taking derivatives:

| Quantity | Formula |
|----------|---------|
| Average energy | $\langle E \rangle = -\frac{\partial \ln Z}{\partial \beta}$ |
| Energy variance | $\text{Var}(E) = \frac{\partial^2 \ln Z}{\partial \beta^2}$ |
| Entropy | $S = k_B (\ln Z + \beta \langle E \rangle)$ |
| Helmholtz free energy | $F = -k_B T \ln Z$ |
| Pressure (if volume-dependent) | $P = k_B T \frac{\partial \ln Z}{\partial V}$ |

The partition function is a **moment-generating function** for the energy distribution: $\ln Z$ is the cumulant-generating function (connecting to the moment-generating function in probability theory — see [measure-theoretic-foundations.md](../probability/measure-theoretic-foundations.md)).

---

## Helmholtz Free Energy

### Definition and Interpretation

$$F = \langle E \rangle - TS = -k_B T \ln Z$$

The free energy balances **energy** (systems prefer low energy) against **entropy** (systems prefer high disorder). Temperature $T$ controls the trade-off:

- $T \to 0$: energy dominates; the system freezes into the ground state
- $T \to \infty$: entropy dominates; the system explores all states uniformly

### Free Energy as a Variational Principle

For any distribution $q(s)$ over microstates, define the **variational free energy**:

$$F[q] = \langle E \rangle_q - T \cdot S[q] = \sum_s q(s) E(s) + k_B T \sum_s q(s) \ln q(s)$$

Rewriting using the KL divergence:

$$F[q] = F_{\text{eq}} + k_B T \cdot D_\text{KL}(q \| p_{\text{eq}})$$

where $p_{\text{eq}}$ is the Boltzmann distribution and $F_{\text{eq}} = -k_B T \ln Z$. Since $D_\text{KL} \geq 0$:

$$F[q] \geq F_{\text{eq}}$$

with equality if and only if $q = p_{\text{eq}}$. The Boltzmann distribution *minimises the variational free energy*. This is the **Gibbs variational principle**, the template for all variational methods.

---

## The Grand Canonical and Other Ensembles

### Grand Canonical Ensemble

When particle number $N$ can fluctuate (open system), introduce the chemical potential $\mu$:

$$p(s) = \frac{1}{\Xi} e^{-\beta(E(s) - \mu N(s))}, \quad \Xi = \sum_s e^{-\beta(E(s) - \mu N(s))}$$

The grand partition function $\Xi$ plays the same role as $Z$, and the grand potential $\Omega = -k_B T \ln \Xi = F - \mu N$ replaces $F$.

### Ensemble Equivalence

In the thermodynamic limit ($N \to \infty$), microcanonical (fixed $E$), canonical (fixed $T$), and grand canonical (fixed $T, \mu$) ensembles give identical predictions for intensive quantities. This follows from concentration of measure: energy fluctuations scale as $O(1/\sqrt{N})$ relative to the mean (see [concentration-inequalities.md](../probability/concentration-inequalities.md)).

---

## Legendre Transforms and Thermodynamic Potentials

The different thermodynamic potentials are related by **Legendre transforms**, which exchange between conjugate variables:

$$F(T, V, N) = E - TS \quad \text{(energy} \leftrightarrow \text{temperature)}$$
$$G(T, P, N) = F + PV \quad \text{(volume} \leftrightarrow \text{pressure)}$$
$$\Omega(T, V, \mu) = F - \mu N \quad \text{(particle number} \leftrightarrow \text{chemical potential)}$$

Each potential is natural in its own variables: $F$ is minimised at fixed $T$; $G$ (Gibbs free energy) is minimised at fixed $T$ and $P$. The Legendre transform structure ensures thermodynamic consistency and appears in many other contexts — convex duality in optimisation, the Fenchel conjugate, and the relationship between rate functions and moment-generating functions in large deviations theory.

---

## Free Energy in Machine Learning and AI

### Variational Inference

In Bayesian inference, the posterior $p(\theta | D) = p(D | \theta) p(\theta) / p(D)$ is often intractable. Variational inference approximates it by minimising:

$$\text{ELBO}(q) = \mathbb{E}_q[\log p(D, \theta)] - \mathbb{E}_q[\log q(\theta)]$$

or equivalently minimising $D_\text{KL}(q(\theta) \| p(\theta | D))$. This is exactly the Gibbs variational principle with:

- $E(\theta) = -\log p(D, \theta)$ as "energy"
- $S[q] = -\mathbb{E}_q[\log q]$ as "entropy"
- $T = 1$ (temperature set by convention)

The ELBO is the negative variational free energy. See [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md).

### Energy-Based Models

Energy-based models (EBMs) define $p(x) = e^{-E_\theta(x)} / Z_\theta$ directly. Training requires estimating $\nabla_\theta \log Z_\theta$, which is intractable in general. Contrastive divergence, score matching, and noise-contrastive estimation are all strategies for avoiding explicit partition function computation.

### Friston's Free Energy Principle

The FEP proposes that biological agents minimise a variational free energy:

$$F = \mathbb{E}_q[\log q(\theta) - \log p(o, \theta)] = D_\text{KL}(q(\theta) \| p(\theta | o)) - \log p(o)$$

where $o$ are observations and $q$ is the agent's approximate posterior ("beliefs"). Since $D_\text{KL} \geq 0$, $F$ is an upper bound on surprisal $-\log p(o)$. The agent minimises $F$ by:

1. **Perception**: Updating $q$ to better approximate $p(\theta | o)$ (reduce $D_\text{KL}$)
2. **Action**: Changing the world to make observations $o$ less surprising (reduce $-\log p(o)$)

This is the same variational structure as the Gibbs principle and the ELBO, applied to embodied agents. The partition function / free energy framework provides the common mathematical substrate.

---

## Critical Phenomena Near $Z$

The partition function reveals phase transitions as **singularities** (non-analyticities) in $\ln Z$ or its derivatives:

- First-order transitions: discontinuity in $\frac{\partial \ln Z}{\partial \beta}$ (latent heat)
- Second-order transitions: divergence in $\frac{\partial^2 \ln Z}{\partial \beta^2}$ (divergent heat capacity/susceptibility)
- In finite systems, $Z$ is a finite sum of exponentials and hence analytic; singularities emerge only in the thermodynamic limit $N \to \infty$

This is why phase transitions are mathematically precise only in infinite systems, and why finite-size scaling is needed to extract critical exponents from simulations (see [ising-model-phase-transitions.md](ising-model-phase-transitions.md)).

---

## Connections

- **Thermodynamic entropy**: The Boltzmann distribution and $Z$ emerge from MaxEnt — see [thermodynamics-entropy-unification.md](thermodynamics-entropy-unification.md)
- **KL divergence**: $F[q] = F_{\text{eq}} + k_B T \cdot D_\text{KL}(q \| p)$ — see [kl-divergence-cross-entropy.md](../information-theory/kl-divergence-cross-entropy.md)
- **Hopfield and Boltzmann machines**: Energy-based models directly implement the $p \propto e^{-E}$ structure — see [hopfield-boltzmann-machines.md](hopfield-boltzmann-machines.md)
- **SDEs and Langevin dynamics**: The Boltzmann distribution is the stationary distribution of Langevin SDEs — see [stochastic-processes-brownian-sde.md](../probability/stochastic-processes-brownian-sde.md)
