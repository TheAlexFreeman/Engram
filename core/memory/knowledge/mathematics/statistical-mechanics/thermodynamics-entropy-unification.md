---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Thermodynamics, Entropy, and the Physics–Information Unification

## Core Idea

Entropy appears in two seemingly independent domains — thermodynamics and information theory — with the same functional form. This is not coincidence: Jaynes (1957) showed that statistical mechanics can be *derived* from information theory via the **maximum entropy principle**, and the second law of thermodynamics can be read as a statement about information loss. The Boltzmann-Gibbs-Shannon unification is one of the deepest bridges in mathematical science, connecting the physics of heat engines to the mathematics of coding theory and Bayesian inference.

---

## Thermodynamic Entropy

### Clausius and Macroscopic Entropy

Clausius (1865) defined entropy as a state function via the reversible heat integral:

$$dS = \frac{\delta Q_{\text{rev}}}{T}$$

The **second law** states that for any process in an isolated system, $\Delta S \geq 0$, with equality only for reversible processes. Entropy is the arrow of time: it distinguishes past from future in a way that the microscopic laws of physics (which are time-reversible) do not.

### Boltzmann Entropy

Boltzmann (1877) provided the microscopic interpretation:

$$S = k_B \ln W$$

where $W$ is the number of microstates compatible with the observed macrostate, and $k_B \approx 1.38 \times 10^{-23}$ J/K is Boltzmann's constant. This relates macroscopic irreversibility to the overwhelming combinatorial majority of disordered microstates. A gas expands to fill its container not because of a force but because there are astronomically more spread-out configurations than concentrated ones.

### Gibbs Entropy

Gibbs generalised Boltzmann's formula to arbitrary probability distributions over microstates:

$$S = -k_B \sum_i p_i \ln p_i$$

This is the entropy of the *ensemble* — the probability distribution we assign to microstates. When all $W$ microstates are equally likely ($p_i = 1/W$), Gibbs entropy reduces to Boltzmann's: $S = k_B \ln W$.

---

## Shannon Entropy

Shannon (1948), working on communication theory with no reference to physics, defined the entropy of a discrete random variable:

$$H(X) = -\sum_i p_i \log_2 p_i$$

This measures the average information content (in bits) of observing the outcome of $X$: the expected number of yes/no questions needed to determine the outcome. See [entropy-source-coding-theorem.md](../information-theory/entropy-source-coding-theorem.md) for the source coding theorem that makes this operational.

The formal identity between Shannon and Gibbs entropy — up to the constant $k_B$ and the choice of logarithm base — was immediately noticed.

---

## The Jaynes Program: MaxEnt

### The Maximum Entropy Principle

Jaynes (1957) reversed the logical direction: instead of deriving entropy from statistical mechanics, he derived statistical mechanics from entropy maximisation.

**Principle:** Given known constraints (e.g., average energy $\langle E \rangle$), the least biased probability distribution is the one that maximises Shannon entropy subject to those constraints.

Using Lagrange multipliers for the constraints $\sum_i p_i = 1$ and $\sum_i p_i E_i = \langle E \rangle$:

$$\mathcal{L} = -\sum_i p_i \ln p_i - \alpha\left(\sum_i p_i - 1\right) - \beta\left(\sum_i p_i E_i - \langle E \rangle\right)$$

Setting $\partial \mathcal{L} / \partial p_i = 0$ yields the **Boltzmann distribution**:

$$p_i = \frac{1}{Z} e^{-\beta E_i}, \quad Z = \sum_i e^{-\beta E_i}$$

where $\beta = 1/k_B T$ is identified with inverse temperature. The partition function $Z$ emerges from normalisation, and the Helmholtz free energy follows as $F = -k_B T \ln Z$.

### What MaxEnt Accomplishes

Jaynes showed that the entire edifice of equilibrium statistical mechanics — the canonical ensemble, the grand canonical ensemble, the Boltzmann distribution — follows from a single information-theoretic principle. Statistical mechanics is not a physical theory about "things bumping into each other" but a *logical inference framework* for reasoning under incomplete information about complex systems.

This reframes the second law: entropy increases not because of some mysterious physical drive but because most probability distributions consistent with macroscopic constraints are high-entropy. The second law is a statement about the overwhelming likelihood of typical configurations.

---

## The Second Law as Information Loss

### Landauer's Principle

Landauer (1961) showed that erasing one bit of information necessarily dissipates at least:

$$W \geq k_B T \ln 2$$

of energy as heat. Information erasure is the fundamental irreversible operation. This resolves Maxwell's demon paradox: the demon must erase its memory to operate cyclically, and that erasure produces exactly enough entropy to satisfy the second law.

### Bennett and Reversible Computation

Bennett (1973) showed that computation can in principle be performed reversibly (with no energy cost), but only if intermediate results are not erased. The thermodynamic cost of computation is not in the computation itself but in the *disposal of information*.

### The Szilard Engine

Szilard (1929) distilled Maxwell's demon to a single-molecule engine:

1. Observe which half of a box a molecule occupies (gain 1 bit)
2. Insert a piston and extract $k_B T \ln 2$ of work from isothermal expansion
3. To reset the demon's memory for the next cycle, erase that 1 bit, costing $k_B T \ln 2$ of work

Net work: zero. The second law holds because measurement and memory erasure are physical processes with thermodynamic costs.

---

## Entropy in Different Frameworks

| Framework | Entropy | Measures | Maximised by |
|-----------|---------|----------|-------------|
| Clausius | $\int \delta Q_{\text{rev}} / T$ | Macroscopic heat flow | Thermal equilibrium |
| Boltzmann | $k_B \ln W$ | Microstate count | Uniform distribution over microstates |
| Gibbs | $-k_B \sum p_i \ln p_i$ | Ensemble uncertainty | Boltzmann distribution (given $\langle E \rangle$) |
| Shannon | $-\sum p_i \log_2 p_i$ | Information content | Uniform distribution (unconstrained) |
| Von Neumann | $-\text{Tr}(\rho \ln \rho)$ | Quantum mixed state uncertainty | Maximally mixed state $\rho = I/d$ |
| Rényi | $\frac{1}{1-\alpha}\log\sum p_i^\alpha$ | Generalised information | — (family parameterised by $\alpha$) |

All converge to the same core idea: entropy measures the number of distinguishable possibilities consistent with what is known. The logarithm ensures additivity for independent systems.

---

## The KL Divergence as Free Energy

The connection between free energy and information deepens through the KL divergence (see [kl-divergence-cross-entropy.md](../information-theory/kl-divergence-cross-entropy.md)):

$$F[q] = \langle E \rangle_q - T \cdot S[q] = k_B T \cdot D_\text{KL}(q \| p_{\text{eq}}) + F_{\text{eq}}$$

where $q$ is any distribution, $p_{\text{eq}}$ is the Boltzmann equilibrium, and $F_{\text{eq}} = -k_B T \ln Z$ is the equilibrium free energy. This means:

- Helmholtz free energy $F[q]$ is the equilibrium free energy plus the KL divergence between $q$ and equilibrium
- Minimising $F[q]$ is equivalent to minimising $D_\text{KL}(q \| p_{\text{eq}})$
- The system relaxes to equilibrium by minimising relative entropy

This variational structure is exactly the form used in Friston's free energy principle (see [partition-function-free-energy.md](partition-function-free-energy.md)) and in variational inference (see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)).

---

## Connections

- **Ergodic theory**: The second law relies on ergodic assumptions for time averages to match ensemble averages — see [ergodic-theory-mixing.md](../dynamical-systems/ergodic-theory-mixing.md)
- **Kolmogorov complexity**: Algorithmic entropy provides a single-object (non-probabilistic) notion of randomness that connects to thermodynamic entropy via the coding theorem — see the information-theory files
