---

created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: high
related:
  - prisoner-dilemma-coordination-games.md
  - extensive-form-games-backward-induction.md
  - evolutionary-game-theory.md
---

# Normal-Form Games and Nash Equilibrium

## Representing Strategic Situations

A **game in normal form** (or strategic form) is a mathematical model of a situation in which:
- A finite set of **players** each choose an action simultaneously (or equivalently, without observing others' choices)
- Each combination of choices produces **payoffs** for every player

**Formal definition.** A normal-form game is a triple $G = (N, S, u)$ where:
- $N = \{1, 2, \ldots, n\}$ is the set of players
- $S = S_1 \times S_2 \times \cdots \times S_n$ where $S_i$ is the set of **pure strategies** available to player $i$
- $u = (u_1, u_2, \ldots, u_n)$ where $u_i : S \to \mathbb{R}$ is player $i$'s **utility function** (payoff)

A **strategy profile** $s = (s_1, s_2, \ldots, s_n) \in S$ specifies one strategy per player. The pair $(u_i(s))$ is the payoff to player $i$ under profile $s$.

### The Payoff Matrix

For two players with finite strategy sets, the game is conveniently represented as a matrix. Rows index Player 1's strategies, columns index Player 2's strategies, and each cell contains the pair $(u_1, u_2)$.

**Prisoner's Dilemma payoff matrix:**

|  | Cooperate (C) | Defect (D) |
|---|---|---|
| **Cooperate (C)** | (3, 3) | (0, 5) |
| **Defect (D)** | (5, 0) | (1, 1) |

Player 1 chooses rows, Player 2 chooses columns. The first number in each cell is Player 1's payoff.

---

## Dominant Strategies

A strategy $s_i$ **strictly dominates** another strategy $s_i'$ if for every possible strategy profile of the other players $s_{-i} \in S_{-i}$:

$$u_i(s_i, s_{-i}) > u_i(s_i', s_{-i})$$

That is, $s_i$ gives player $i$ a strictly higher payoff regardless of what others do. A rational player will never play a strictly dominated strategy — they can always unilaterally improve by switching.

**Iterated elimination of strictly dominated strategies (IESDS):** Remove all strictly dominated strategies from the game, reduce the strategy sets, and repeat. Whatever survives IESDS is "rationalizable" — consistent with common knowledge of rationality.

In some games (like the Prisoner's Dilemma), IESDS yields a unique prediction. In most games, many strategies survive IESDS, and a sharper solution concept is needed.

---

## Nash Equilibrium

**Definition.** A strategy profile $s^* = (s_1^*, s_2^*, \ldots, s_n^*)$ is a **Nash equilibrium** if for every player $i$ and every alternative strategy $s_i \in S_i$:

$$u_i(s_i^*, s_{-i}^*) \geq u_i(s_i, s_{-i}^*)$$

No player can improve their payoff by **unilaterally deviating** from $s^*$, given that all other players play according to $s^*$.

Nash equilibrium is a **fixed point** condition: if each player is best-responding to the others, no player has an incentive to deviate. It is not, in general, socially optimal — the Prisoner's Dilemma has a unique Nash equilibrium at (Defect, Defect), which is Pareto-dominated by (Cooperate, Cooperate).

### Pure vs. Mixed strategies

A **pure strategy** assigns probability 1 to a single action. A **mixed strategy** $\sigma_i$ is a probability distribution over $S_i$:

$$\sigma_i \in \Delta(S_i) = \left\{ \sigma_i : S_i \to [0,1] \;\middle|\; \sum_{s_i \in S_i} \sigma_i(s_i) = 1 \right\}$$

The **expected payoff** under mixed strategy profile $\sigma = (\sigma_1, \ldots, \sigma_n)$ is:

$$u_i(\sigma) = \sum_{s \in S} \left( \prod_{j \in N} \sigma_j(s_j) \right) u_i(s)$$

A **mixed strategy Nash equilibrium (MSNE)** requires each player's mixed strategy to be a best response to the others' mixed strategies. In a MSNE, any pure strategy that is played with positive probability must yield the same expected payoff as any other such strategy — otherwise the player would shift probability mass toward the better-performing strategy.

---

## Nash's Existence Theorem

**Theorem (Nash, 1950).** Every finite game (finite player set, finite strategy sets) has at least one Nash equilibrium, possibly in mixed strategies.

**Proof sketch.** Define the **best-response correspondence** $\text{BR}_i(\sigma_{-i})$ as the set of all mixed strategies that maximize player $i$'s expected payoff given $\sigma_{-i}$. The joint best-response correspondence:

$$\text{BR}(\sigma) = \prod_{i \in N} \text{BR}_i(\sigma_{-i})$$

maps strategy profiles to sets of strategy profiles. Nash showed that $\text{BR}$ satisfies the conditions of **Kakutani's fixed-point theorem** (a generalization of Brouwer's theorem to correspondences):
1. The strategy space $\prod_i \Delta(S_i)$ is a nonempty, compact, convex subset of a Euclidean space
2. $\text{BR}$ is nonempty-valued (a best response always exists, by compactness/continuity)
3. $\text{BR}$ is convex-valued (if two strategies are best responses, any mixture is too)
4. $\text{BR}$ has a closed graph

Therefore, $\text{BR}$ has a fixed point $\sigma^* \in \text{BR}(\sigma^*)$, which is by definition a Nash equilibrium. $\square$

**Significance:** Nash's theorem guarantees existence without proving uniqueness or providing a constructive algorithm. Games generically have equilibria, but may have many; finding or selecting among them is a separate problem.

---

## Limitations of Nash Equilibrium

**1. Multiplicity.** Most games have multiple Nash equilibria. The Battle of the Sexes has three (two pure, one mixed). Without a selection principle, Nash equilibrium does not predict a unique outcome.

**2. Refinements.** Some Nash equilibria rely on non-credible threats, particularly in sequential games. Nash equilibria can be "supported" by threats that rational agents would never carry out. Refinements like **subgame perfect equilibrium** (Selten, 1965) and **trembling-hand perfect equilibrium** attempt to eliminate implausible equilibria.

**3. No dynamics.** Nash equilibrium describes a rest point of some unspecified adjustment process, but says nothing about *how* equilibrium is reached, or whether it would be reached at all. Evolutionary game theory addresses this gap.

**4. Computational complexity.** Computing a Nash equilibrium is PPAD-complete (Chen & Deng, 2006; Daskalakis et al., 2009) — in the hardness class for which efficient algorithms are believed not to exist — even for two-player games. Finding equilibria in large games is computationally intractable in the worst case.

**5. Behavioral deviations.** Experimental economics consistently finds that humans deviate from Nash predictions in systematic ways — cooperation in prisoner's dilemmas, overbidding in winner's curse settings, limited backward induction in centipede games. Bounded rationality, fairness norms, and limited strategic sophistication explain many deviations.

---

## Applications to AI

**Multi-agent reinforcement learning.** When multiple RL agents train simultaneously in a shared environment, the system's dynamics are a game. Nash equilibria are natural solution concepts, but finding them requires coordination on which equilibrium to play (the equilibrium selection problem).

**Mechanism design.** Understanding what Nash equilibria arise under a given set of rules (mechanism) is the first step to designing rules that produce desired equilibria. Most mechanism design results characterize what outcomes are "implementable in dominant strategies" or "implementable in Bayes-Nash equilibrium."

**Reward hacking.** If a model's objective is a proxy for what humans intend, the model plays a game against the evaluation mechanism. Nash-equilibrium analysis predicts that sufficiently capable models will exploit systematic weaknesses in proxy objectives — the Goodhart's Law problem restated in game-theoretic terms.

---

## Key concepts summary

| Concept | Statement |
|---|---|
| Normal-form game | $(N, S, u)$: players, strategy sets, payoff functions |
| Strict dominance | $s_i$ dominates $s_i'$ if $u_i(s_i, s_{-i}) > u_i(s_i', s_{-i})$ for all $s_{-i}$ |
| Nash equilibrium | No player improves by unilateral deviation |
| Mixed strategy NE | Equilibrium in probability distributions over strategies |
| Nash's theorem | Every finite game has at least one NE (possibly mixed) |
| Refinements | Subgame perfection, trembling-hand eliminate implausible NE |

---

## See also

- `prisoner-dilemma-coordination-games.md` — key games that reveal the structure of social dilemmas
- `extensive-form-games-backward-induction.md` — sequential games and subgame perfect equilibrium
- `mechanism-design-revelation-principle.md` — designing rules that produce desired Nash equilibria