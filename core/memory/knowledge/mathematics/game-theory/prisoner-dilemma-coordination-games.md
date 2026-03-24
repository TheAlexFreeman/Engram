---

created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: high
related:
  - normal-form-games-nash-equilibrium.md
  - evolution-of-cooperation.md
  - evolutionary-game-theory.md
---

# Prisoner's Dilemma and Coordination Games

## The Prisoner's Dilemma

### Structure

The **Prisoner's Dilemma** is a two-player game that captures the fundamental tension between individual rationality and collective welfare. Two players simultaneously choose to either **Cooperate (C)** or **Defect (D)**:

|  | C | D |
|---|---|---|
| **C** | (R, R) | (S, T) |
| **D** | (T, S) | (P, P) |

The payoff ranking that defines a Prisoner's Dilemma is: $T > R > P > S$

- $T$ = Temptation (best unilateral defection outcome)
- $R$ = Reward (mutual cooperation)
- $P$ = Punishment (mutual defection)
- $S$ = Sucker (cooperating while the other defects)

A canonical example: $T = 5, R = 3, P = 1, S = 0$.

### Why defection dominates

No matter what the other player does:
- If they Cooperate: Defect yields $T = 5$ vs. Cooperate yields $R = 3$. Defect is better.
- If they Defect: Defect yields $P = 1$ vs. Cooperate yields $S = 0$. Defect is better.

Defect **strictly dominates** Cooperate for both players. By dominance reasoning, rational players defect. The unique Nash equilibrium is (D, D), yielding (P, P) = (1, 1). But mutual cooperation (C, C) would yield (R, R) = (3, 3) for both — strictly Pareto-better.

The Prisoner's Dilemma formalizes the intuition: **individually rational behavior can be collectively irrational.** This is not a failure of rationality but a consequence of the payoff structure. Fixing the outcome requires changing the game — either the payoffs (e.g., through binding agreements), the information structure, or the iteration of the game.

### Moral: The problem is structural

The tragedy of the Prisoner's Dilemma is that it captures many real social situations — arms races, climate negotiation, open-source contribution, overfishing, AI capability races. The common factor is:
1. Each agent's dominant strategy harms collective welfare
2. No agent can unilaterally improve the collective outcome
3. The bad outcome is a stable equilibrium — no single agent can escape it by changing their behavior alone

Escaping the Prisoner's Dilemma requires **institutional design**: changing the payoff structure (subsidies, punishments), enabling binding agreements, or changing the game from one-shot to repeated.

---

## The Folk Theorem: Repeated Games and Cooperation

### Setup

Suppose the Prisoner's Dilemma is played **infinitely many times** by the same players, each of whom discounts future payoffs by a discount factor $\delta \in (0, 1)$. Player $i$'s total payoff from an infinite stream of stage-game payoffs $(u_t)_{t=0}^\infty$ is:

$$(1-\delta) \sum_{t=0}^{\infty} \delta^t u_t$$

The factor $(1-\delta)$ normalizes the average to the stage-game payoff scale. $\delta$ close to 1 means the future is valued almost as much as the present; $\delta$ close to 0 means only the current period matters.

### The Folk Theorem

**Theorem (informal).** In an infinitely repeated game, if players are sufficiently patient (i.e., $\delta$ is sufficiently close to 1), *any* individually rational, feasible payoff vector can be sustained as a Nash equilibrium.

A payoff vector is **individually rational** if each player obtains at least their **minimax payoff** — the lowest the other players can hold them to, even if the player best-responds. A payoff is **feasible** if it lies in the convex hull of stage-game payoff vectors.

**Application to the Prisoner's Dilemma.** Mutual cooperation (R, R) = (3, 3) is individually rational (both players' minimax payoffs are P = 1 < R = 3). The Folk Theorem implies that for large enough $\delta$, (Cooperate forever) can be sustained as a Nash equilibrium by the **grim trigger strategy**:

> Play C in period 0. Continue playing C as long as no one has ever defected. If anyone ever defects, play D forever.

If both players use grim trigger, cooperation is sustained provided deviation is not profitable:
$$\frac{R}{1-\delta} \geq T + \frac{P \cdot \delta}{1-\delta}$$

Rearranging: $\delta \geq \frac{T - R}{T - P}$. For T=5, R=3, P=1: $\delta \geq \frac{2}{4} = 0.5$. Cooperation is sustainable whenever $\delta \geq 0.5$.

**Caveat.** The Folk Theorem establishes existence, not uniqueness — infinitely repeated games have vastly more equilibria than one-shot games (including many bad ones). The challenge is equilibrium selection, not existence of cooperation.

---

## Coordination Games

### Structure: Multiple Equilibria

A **coordination game** is one with multiple Nash equilibria, where players strictly prefer to coordinate (play the same equilibrium) but face the problem of which equilibrium to select. Unlike the Prisoner's Dilemma (where the hard problem was cooperation), here the hard problem is **coordination** — even fully cooperative agents may fail to coordinate.

### Battle of the Sexes

|  | Opera (O) | Football (F) |
|---|---|---|
| **Opera (O)** | (2, 1) | (0, 0) |
| **Football (F)** | (0, 0) | (1, 2) |

Player 1 prefers Opera; Player 2 prefers Football; both prefer to be together over apart. Three Nash equilibria: (O, O), (F, F), and a mixed strategy equilibrium. Conflict over which equilibrium to select.

### Stag Hunt

|  | Stag (S) | Hare (H) |
|---|---|---|
| **Stag (S)** | (4, 4) | (0, 2) |
| **Hare (H)** | (2, 0) | (2, 2) |

Two Nash equilibria: (Stag, Stag) — cooperative and Pareto-superior — and (Hare, Hare) — safe but Pareto-inferior. Unlike the Prisoner's Dilemma, both players want to hunt Stag together; the problem is risk: if the other player hunts Hare, hunting Stag yields 0.

**Risk dominance.** (Hare, Hare) is **risk dominant**: it is the best response when the other player's strategy is uncertain (uniform prior over Stag/Hare). Risk-dominant equilibria are often selected in practice even when Pareto-dominated. Harsanyi and Selten (1988) proposed risk dominance as an equilibrium selection criterion.

The Stag Hunt is a better model than the Prisoner's Dilemma for many AI coordination problems: the key challenge is not temptation to defect but *trust* that the other party will also cooperate with you.

### Public Goods Game

A generalization to $n$ players: each contributes some amount to a public good that benefits all proportionally. The social optimum is full contribution; individually rational play is zero contribution (dominant strategy). The $n$-player version of the Prisoner's Dilemma.

---

## Schelling Points (Focal Points)

**Thomas Schelling** (1960) observed that in coordination games, equilibrium selection often proceeds not through explicit negotiation but through **salience** — some equilibria stand out as focal for cultural, contextual, or geometric reasons.

**Classic example (Schelling's experiment).** Subjects asked: "If you had to meet a stranger in New York City tomorrow, without any prior communication, where and when would you go?" Most answered: Grand Central Terminal, at noon. No one specified these in the problem — they were focal because of their salience.

**Key insight.** Schelling points are equilibria selected by **common knowledge of context**, not by dominance or Pareto arguments. In games with multiple equilibria, shared culture, convention, and history supply focal selection devices that pure game theory cannot.

**Implications:** Language is a Schelling-point system — words acquire meanings because of common expectations about their use. Conventions (driving on the right, metric vs. imperial) persist not because they're optimal but because coordination on any standard is better than no coordination.

---

## Application to AI Safety: Competitive AI Development

### The AI Race as a Prisoner's Dilemma

Competitive AI development between multiple labs (or nations) has the structure of a Prisoner's Dilemma over safety investment:
- **Cooperate** = invest in safety, accept some development slowdown
- **Defect** = minimize safety investment, maximize capability development speed

Payoff structure (when safety is costly and capability confers competitive advantage):
- If both invest in safety (C, C): both slower, catastrophic risk reduced — good collective outcome
- If one defects on safety (D, C): defector gains competitive lead — best unilateral outcome
- If neither invests in safety (D, D): race with catastrophic risk maintained — bad collective outcome
- If one cooperates alone (C, D): competitive disadvantage plus shared catastrophic risk — worst outcome

This is $T > R > P > S$: a Prisoner's Dilemma structure. Individual rationality drives defection on safety.

**The Folk Theorem's implications.** If the same labs/nations compete repeatedly over a long horizon (high $\delta$), cooperation is sustainable in principle. The question is whether the discount factor is high enough and whether there are mechanisms for binding agreements.

**Mechanism design response.** Changing the payoff structure through:
1. International agreements with credible enforcement (change P and T values)
2. Safety requirements as a condition of operating (change strategy sets)
3. Liability regimes that shift the cost of catastrophe from shared to private (change payoffs)
4. Transparency regimes that enable punishment in repeated play (enable grim trigger)

### Coordination Games in Multi-Agent AI

When multiple AI agents work together, coordination game structures arise:
- Multiple valid conventions (naming, signaling, role assignment) — Battle of the Sexes type
- Trust-dependent cooperation (tool sharing, information pooling) — Stag Hunt type
- Focal points: shared training data, common prompting conventions, and language itself serve as focal equilibrium selectors in multi-agent AI

---

## Summary

| Game | Structure | Equilibrium | Challenge |
|---|---|---|---|
| Prisoner's Dilemma | $T > R > P > S$ | Unique: (D, D) — Pareto-dominated | Individual rationality vs. collective welfare |
| Battle of the Sexes | Prefer coordination, conflict about which | Three NE (incl. mixed) | Which equilibrium to select |
| Stag Hunt | Cooperative optimum is Pareto-better | Two pure NE: cooperative and safe | Trust and risk — coordination failure despite shared interests |
| Public Goods Game | $n$-player generalization of PD | Zero contribution dominant | Collective action problem |

The key insight unifying these is that **social outcomes are equilibria, not just choices.** Changing the outcome requires either changing the payoff structure (mechanism design) or changing the equilibrium selection (through communication, convention, or commitment).

---

## See also

- `normal-form-games-nash-equilibrium.md` — foundational definitions
- `evolutionary-game-theory.md` — dynamics of which equilibrium gets selected in populations
- `evolution-of-cooperation.md` — Axelrod's tournament and the conditions for cooperation
- `mechanism-design-revelation-principle.md` — changing the rules to change equilibria