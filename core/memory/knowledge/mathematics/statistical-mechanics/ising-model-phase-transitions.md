---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# The Ising Model and Phase Transitions

## Core Idea

The **Ising model** is the simplest non-trivial statistical mechanical system that exhibits a **phase transition** — a qualitative change in macroscopic behaviour at a critical temperature. Binary spins on a lattice with nearest-neighbour interactions produce ferromagnetic order below a critical temperature $T_c$ and disorder above it. Onsager's exact solution of the 2D Ising model (1944) was one of the great triumphs of mathematical physics, and the model has become the paradigmatic laboratory for studying critical phenomena, universality, renormalisation, and mean-field approximations. Its mathematical structure reappears in neural networks (Hopfield/Boltzmann machines), social dynamics, and combinatorial optimisation.

---

## The Model

### Setup

$N$ binary spins $\sigma_i \in \{+1, -1\}$ arranged on a $d$-dimensional lattice with nearest-neighbour coupling:

$$H(\boldsymbol{\sigma}) = -J \sum_{\langle i,j \rangle} \sigma_i \sigma_j - h \sum_i \sigma_i$$

- $J > 0$: ferromagnetic coupling (aligned spins are lower energy)
- $h$: external magnetic field
- $\langle i,j \rangle$: sum over nearest-neighbour pairs

The Boltzmann distribution gives the probability of configuration $\boldsymbol{\sigma}$:

$$p(\boldsymbol{\sigma}) = \frac{1}{Z} e^{-\beta H(\boldsymbol{\sigma})}, \quad Z = \sum_{\boldsymbol{\sigma}} e^{-\beta H(\boldsymbol{\sigma})}$$

The partition function $Z$ is a sum over $2^N$ configurations — tractable only in special cases (see [partition-function-free-energy.md](partition-function-free-energy.md)).

### Order Parameter

The **magnetisation** $m = \frac{1}{N}\sum_i \langle \sigma_i \rangle$ serves as the order parameter:

- $m = 0$: disordered (paramagnetic) phase
- $m \neq 0$: ordered (ferromagnetic) phase with spontaneous symmetry breaking

---

## Exact Solutions and Dimensions

### 1D Ising Model

Exactly solvable by transfer matrices. Result: no phase transition at any finite temperature. The correlation length $\xi \sim e^{2\beta J}$ grows but never diverges. This illustrates that thermal fluctuations destroy long-range order in one dimension — a consequence of the Mermin-Wagner theorem for continuous symmetries, here applicable to the discrete $\mathbb{Z}_2$ symmetry by domain-wall arguments.

### 2D Ising Model — Onsager's Solution (1944)

Onsager computed $Z$ exactly using transfer matrix methods and algebraic techniques. Key results:

- **Critical temperature**: $\beta_c J = \frac{1}{2}\ln(1 + \sqrt{2}) \approx 0.4407$, so $k_B T_c / J \approx 2.269$
- **Spontaneous magnetisation** (Yang, 1952): $m(T) = \left(1 - \sinh^{-4}(2\beta J)\right)^{1/8}$ for $T < T_c$
- **Specific heat**: Logarithmic divergence $C \sim -\ln|T - T_c|$ at $T_c$
- **Critical exponents**: $\alpha = 0$ (log), $\beta = 1/8$, $\gamma = 7/4$, $\nu = 1$

### 3D and Higher

No exact solution is known for $d \geq 3$. The 3D Ising model is studied by Monte Carlo simulation, series expansions, and the conformal bootstrap (which recently determined critical exponents to extraordinary precision). Mean-field theory becomes exact above $d = 4$ (the upper critical dimension).

---

## The Mean-Field Approximation

### Weiss Molecular Field Theory

Replace the interaction of spin $i$ with its neighbours by an interaction with the average magnetisation:

$$\langle \sigma_i \rangle = \tanh(\beta(zJm + h))$$

where $z$ is the coordination number (number of nearest neighbours). The self-consistency condition $m = \tanh(\beta z J m)$ (for $h = 0$) gives:

- $T > T_c^{\text{MF}} = zJ/k_B$: only $m = 0$ solution (paramagnetic)
- $T < T_c^{\text{MF}}$: non-zero $m$ solutions emerge via pitchfork bifurcation (see [bifurcation-theory-catastrophe.md](../dynamical-systems/bifurcation-theory-catastrophe.md))

Mean-field exponents: $\alpha = 0$, $\beta = 1/2$, $\gamma = 1$, $\delta = 3$. These are dimension-independent and become exact for $d > 4$.

### Landau Theory

Landau (1937) approximated the free energy as a polynomial in the order parameter:

$$F(m) = F_0 + a(T - T_c) m^2 + b m^4 + \cdots$$

The phase transition occurs when the coefficient of $m^2$ changes sign. This is equivalent to mean-field theory and to catastrophe theory's cusp catastrophe (see bifurcation-theory-catastrophe.md). Landau theory correctly captures the qualitative structure of continuous phase transitions but misses critical fluctuations.

---

## Critical Phenomena and Universality

### Power Laws at Criticality

Near $T_c$, physical quantities follow power laws characterised by **critical exponents**:

| Quantity | Behaviour | Exponent |
|----------|-----------|----------|
| Magnetisation | $m \sim |T - T_c|^\beta$ | $\beta$ |
| Susceptibility | $\chi \sim |T - T_c|^{-\gamma}$ | $\gamma$ |
| Correlation length | $\xi \sim |T - T_c|^{-\nu}$ | $\nu$ |
| Specific heat | $C \sim |T - T_c|^{-\alpha}$ | $\alpha$ |
| Correlation function at $T_c$ | $\langle \sigma_0 \sigma_r \rangle \sim r^{-(d-2+\eta)}$ | $\eta$ |

### Universality

Systems with entirely different microscopic details (Ising spins, lattice gases, binary alloys, even the liquid-gas transition near the critical point) share the same critical exponents if they have:

1. The same **spatial dimension** $d$
2. The same **symmetry** of the order parameter
3. The same **range** of interactions (short vs long range)

This is universality: microscopic details are irrelevant; only symmetry and dimension matter. The Ising universality class ($\mathbb{Z}_2$ symmetry, short-range, $d$ dimensions) is the most studied.

### Renormalisation Group

Kadanoff (1966) and Wilson (1971) explained universality through the **renormalisation group** (RG): coarse-grain the system by integrating out short-wavelength fluctuations. Under this flow, different microscopic models converge to the same **fixed point**, which determines the critical exponents.

The RG flow operates on the space of Hamiltonians (or coupling constants). Fixed points correspond to scale-invariant theories; relevant directions at the fixed point determine the universality class. The upper critical dimension $d_c = 4$ marks where Gaussian (mean-field) fluctuations become sufficient.

### Scaling Relations

Critical exponents are not independent. Scaling relations connect them:

- **Rushbrooke**: $\alpha + 2\beta + \gamma = 2$
- **Josephson** (hyperscaling): $d\nu = 2 - \alpha$
- **Fisher**: $\gamma = (2 - \eta)\nu$

These follow from the assumption that near $T_c$, the free energy is a generalised homogeneous function of the reduced temperature and field.

---

## Phase Transitions as Mathematical Phenomena

Phase transitions are **non-analyticities** in the free energy as a function of external parameters. In finite systems, the partition function $Z$ is a finite sum of analytic functions, hence analytic. Non-analyticity requires the thermodynamic limit $N \to \infty$.

The **Lee-Yang theorem** (1952) locates the zeros of $Z$ in the complex $h$-plane. In finite systems, zeros lie off the real axis; at the phase transition, they pinch the real axis as $N \to \infty$. This provides a rigorous characterisation of where and how phase transitions occur.

Self-organized criticality (see [self-organized-criticality.md](../dynamical-systems/self-organized-criticality.md)) asks why systems in nature appear to sit at or near critical points without fine-tuning of an external parameter like temperature.

---

## The Ising Model Beyond Physics

### Neural Networks

The Hopfield network (see [hopfield-boltzmann-machines.md](hopfield-boltzmann-machines.md)) is an Ising model with learned couplings $J_{ij}$ determined by stored patterns. Pattern retrieval corresponds to relaxation to a low-energy attractor — the spin glass perspective (see [spin-glasses-replica-method.md](spin-glasses-replica-method.md)) becomes essential when storage capacity is pushed.

### Combinatorial Optimisation

MAX-CUT, graph colouring, and satisfiability problems can be mapped to Ising Hamiltonians. Simulated annealing (Kirkpatrick et al., 1983) exploits this: slowly lower $T$ to find the ground state of a combinatorial "energy landscape."

### Social Dynamics

Voter models, opinion dynamics, and cultural diffusion can be formulated as Ising-type models on social networks (see [complex-networks-small-world-scale-free.md](../dynamical-systems/complex-networks-small-world-scale-free.md)). Phase transitions correspond to consensus formation or fragmentation.

---

## Connections

- **Thermodynamic entropy**: The Ising model illustrates the Boltzmann-Gibbs entropy framework and the energy-entropy competition — see [thermodynamics-entropy-unification.md](thermodynamics-entropy-unification.md)
- **MCMC**: The Metropolis algorithm was originally developed to simulate the Ising model — see [markov-chains-mixing-times.md](../probability/markov-chains-mixing-times.md)
