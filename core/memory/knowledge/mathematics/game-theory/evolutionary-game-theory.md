---

created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: high
related:
  - evolution-of-cooperation.md
  - normal-form-games-nash-equilibrium.md
  - prisoner-dilemma-coordination-games.md
---

# Evolutionary Game Theory and Replicator Dynamics

## Motivation: Population-Level Dynamics

Classical game theory asks what strategy a *rational individual* should play. Evolutionary game theory (EGT) rephrases the question: in a **population of agents** that interact repeatedly and update their strategies based on relative success, what strategy distribution does the population converge to?

The evolutionary framing abandons the assumption of hyper-rationality. Instead of computing Nash equilibria by logical deduction, strategies spread or contract through a **selection mechanism**: strategies that do better than average become more common; strategies that do worse become rarer. This connects game theory to population biology, learning dynamics, and cultural evolution.

**Key shift in interpretation:**
- Classical: a strategy is chosen by a rational agent for a single interaction
- Evolutionary: strategies are inherited/learned behaviors; fitness determines relative frequency

---

## Evolutionary Stable Strategy (ESS)

**Definition (Maynard Smith & Price, 1973).** A strategy $s^*$ is an **evolutionarily stable strategy (ESS)** if it can resist invasion by any mutant strategy $s'$ present in small frequency. Formally, for every $s' \neq s^*$ there exists $\bar{\epsilon}_{s'} > 0$ such that for all $\epsilon \in (0, \bar{\epsilon}_{s'})$:

$$u(s^*, \epsilon s' + (1-\epsilon) s^*) > u(s', \epsilon s' + (1-\epsilon) s^*)$$

That is, when the population is mostly playing $s^*$ with a small fraction $\epsilon$ playing the mutant $s'$, $s^*$ does strictly better than $s'$ against the population mixture.

**Relation to Nash equilibrium.** Every ESS is a Nash equilibrium, but not every Nash equilibrium is an ESS. ESS adds a *stability* condition: the equilibrium must be robust to small perturbations in population composition.

**Simpler sufficient conditions.** Strategy $s^*$ is an ESS if either:
1. $u(s^*, s^*) > u(s', s^*)$ for all $s' \neq s^*$ (strict Nash — $s^*$ beats all mutants head-to-head)
2. $u(s^*, s^*) = u(s', s^*)$ and $u(s^*, s') > u(s', s')$ (tie against each other but $s^*$ beats the mutant when matched against itself)

The second condition reflects that if mutants do as well as residents in direct play, what matters is how each does when facing the *mutant itself* — whether the incumbent strategy "defends" itself better against the mutant than the mutant can.

---

## Replicator Dynamics

### Setup

Consider a **single population** of agents, each playing a pure strategy from a finite set $S = \{1, \ldots, k\}$. Let $x_i(t) \geq 0$ be the frequency (fraction) of strategy $i$ at time $t$, with $\sum_i x_i = 1$.

Let $f_i(x)$ be the **fitness** of strategy $i$ in population state $x$:

$$f_i(x) = \sum_{j=1}^k a_{ij} x_j$$

where $a_{ij}$ is the payoff to strategy $i$ when meeting strategy $j$ (the payoff matrix entry). The **average fitness** of the population is:

$$\bar{f}(x) = \sum_i x_i f_i(x) = x^\top A x$$

The **replicator dynamic** is the differential equation:

$$\dot{x}_i = x_i\left(f_i(x) - \bar{f}(x)\right)$$

### Interpretation

The frequency of strategy $i$ grows when its fitness exceeds the population average and shrinks when below average. Strategies at zero frequency stay at zero (no spontaneous mutation); strategies at 1 stay at 1.

**Properties:**
- The state simplex $\Delta = \{x \geq 0 : \sum x_i = 1\}$ is forward-invariant
- Rest points of the replicator dynamic include all **Nash equilibria** of the symmetric two-player game defined by $A$
- Every **ESS** is a **locally asymptotically stable** rest point of the replicator dynamic
- The replicator dynamic is a special case of selection dynamics in evolutionary biology (where fitness drives reproduction)

### Hawk-Dove Game

The **Hawk-Dove** game models conflict over a resource:

- **Hawks (H)**: escalate conflict, fight until winning or badly injured
- **Doves (D)**: display but never fight; retreat if opponent escalates

Payoff matrix (V = resource value, C = cost of injury, $C > V > 0$):

|  | Hawk | Dove |
|---|---|---|
| **Hawk** | $\frac{V-C}{2}$ | $V$ |
| **Dove** | $0$ | $\frac{V}{2}$ |

**Nash equilibria by case:**
- $V > C$: fighting is cheap relative to the prize; Hawk strictly dominates → (Hawk, Hawk) is the unique NE
- $V < C$ (typical case): no pure strategy ESS; the unique ESS is the **mixed strategy** $p^* = V/C$ (fraction Hawk)

**Replicator dynamics.** With $C > V$, the mixed ESS $p^* = V/C$ is globally stable on the interior of [0,1]: Hawk frequency increases when below $p^*$ (expected payoff of Hawk exceeds Dove) and decreases when above. The population converges to a **polymorphic equilibrium** with both strategies present.

**Interpretation.** Animal populations exhibit stable mixes of aggressive and submissive organisms. The Hawk-Dove model predicts that the degree of aggression observed should scale with $V/C$ — and empirical studies broadly confirm this. The ESS captures the population-level outcome without assuming individuals compute Nash equilibria.

---

## Connection to Machine Learning

### Gradient Descent as Replicator Dynamics

The replicator dynamic and gradient descent (with small learning rate) are formally analogous in several ways:
- **Neural network training with softmax output**: adjusting parameters to increase the probability of high-reward outputs is structurally similar to the replicator equation where successful strategies increase in frequency
- **Multiplicative weights update (MWU)**: a discrete-time learning rule closely related to the replicator dynamic; MWU with exponential weights is the discrete analog of the replicator dynamic

Formally: let $w_i > 0$ be the weight of strategy $i$, updated by $w_i(t+1) = w_i(t) \cdot \exp(\eta \cdot f_i(x(t)))$ and then renormalized. As $\eta \to 0$, this converges to the replicator dynamic.

### Multi-Population Replicator Dynamics and Adversarial Training

For a **two-population** setting (e.g., a model population M and a red-team population R):

$$\dot{x}_i = x_i\left(\sum_j A_{ij} y_j - x^\top A y\right) \quad (\text{model strategies } i)$$
$$\dot{y}_j = y_j\left(\sum_i B_{ij} x_i - x^\top B^\top y\right) \quad (\text{red-team strategies } j)$$

where $A$ is the model's payoff matrix and $B$ is the red-team's payoff matrix (often $B = -A$ in zero-sum cases).

In a **zero-sum game** ($B = -A$), the two-population replicator dynamic exhibits **cycling** behavior near Nash equilibria rather than convergence. This corresponds to the well-known instability of adversarial training (GAN training) — the generator and discriminator cycle rather than converging to equilibrium. Understanding this connection has motivated alternative training procedures (e.g., WGAN, gradient penalties) designed to stabilize the dynamics.

### Neural Architecture Search as Strategy Evolution

NAS can be viewed as evolutionary search over strategy space:
- **Population**: candidate architectures
- **Fitness**: validation performance
- **Selection**: retain high-fitness architectures, discard low-fitness ones
- **Mutation/crossover**: generate new candidates from existing ones

This is not replicator dynamics exactly (populations don't mix continuously), but shares the selection-variation-retention structure.

---

## Summary

| Concept | Definition | Significance |
|---|---|---|
| ESS | Strategy resistant to mutant invasion | Population-stable strategy; refinement of Nash |
| Replicator dynamic | $\dot{x}_i = x_i(f_i - \bar{f})$ | Selection dynamics; frequency of strategies evolves |
| Hawk-Dove game | Aggression vs. display; no pure ESS when $C > V$ | Stable mixed equilibria without convex optimization |
| ESS → stable rest point | Every ESS is locally stable under replicator dynamic | Connects evolutionary stability to dynamical systems |
| Gradient descent ~ replicator | Multiplicative weights converge to replicator | Unifies ML training and evolutionary game theory |

---

## See also

- `normal-form-games-nash-equilibrium.md` — Nash equilibrium and its relationship to ESS
- `evolution-of-cooperation.md` — Axelrod's tournament and the evolution of cooperation via replicator-like dynamics
- `prisoner-dilemma-coordination-games.md` — the Prisoner's Dilemma analyzed as a population game